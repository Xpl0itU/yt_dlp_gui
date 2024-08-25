import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QHBoxLayout,
)
from PySide6.QtCore import QThread, Signal
import yt_dlp
import math
from user_data import get_user_data_dir

CUSTOM_FORMAT_JSON_PATH = os.path.join(get_user_data_dir(), "custom_formats.json")


class DownloadWorker(QThread):
    progress_signal = Signal(str, int)

    def __init__(self, queue_manager, output_path, on_finish, format_preset):
        super().__init__()
        self.queue_manager = queue_manager
        self.output_path = output_path
        self.on_finish = on_finish
        self.format_preset = format_preset

    def run(self):
        postprocessor_args = self.format_preset.get("postprocessor_args", [])
        ydl_opts = {
            "format": self.format_preset["format"],
            "outtmpl": os.path.join(self.output_path, "%(title)s.%(ext)s"),
            "progress_hooks": [self.progress_hook],
            "writesubtitles": True,
            "subtitleslangs": [],
            "postprocessors": postprocessor_args,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            while not self.queue_manager.is_empty():
                video_info = self.queue_manager.pop()
                title, url, download_subs, subs_lang = (
                    video_info["title"],
                    video_info["url"],
                    video_info["download_subs"],
                    video_info["subs_lang"],
                )
                if download_subs and subs_lang:
                    ydl_opts["subtitleslangs"] = [subs_lang]
                self.progress_signal.emit(f"Downloading: {title}", 0)
                ydl.download([url])
                self.progress_signal.emit(f"Download completed: {title}", 100)
            self.on_finish()

    def progress_hook(self, d):
        if d.get("status") == "downloading":
            total_bytes = d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes")
            if total_bytes and downloaded_bytes:
                self.progress_signal.emit(
                    None, math.floor(downloaded_bytes / total_bytes * 100)
                )


class QueueManager(QWidget):
    def __init__(self, parent_obj=None, custom_formats=None):
        super().__init__()

        self.queue = []
        self.worker = None
        self.parent_obj = parent_obj
        self.custom_formats = custom_formats if custom_formats else []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(
            ["Title", "URL", "Download Subs", "Subs Language", "Format Preset"]
        )

        buttons_layout = QHBoxLayout()
        self.remove_button = QPushButton(
            "Remove Selected", clicked=self.remove_selected
        )
        self.start_button = QPushButton("Start Download", clicked=self.start_download)
        layout.addWidget(self.table_widget)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addWidget(self.start_button)
        layout.addLayout(buttons_layout)

    def add_video(self, title, url, download_subs, subs_lang, format_preset):
        self.queue.append(
            {
                "title": title,
                "url": url,
                "download_subs": download_subs,
                "subs_lang": subs_lang,
                "format_preset": format_preset,
            }
        )
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)
        self.table_widget.setItem(row_position, 0, QTableWidgetItem(title))
        self.table_widget.setItem(row_position, 1, QTableWidgetItem(url))
        self.table_widget.setItem(row_position, 2, QTableWidgetItem(str(download_subs)))
        self.table_widget.setItem(row_position, 3, QTableWidgetItem(subs_lang))
        self.table_widget.setItem(
            row_position, 4, QTableWidgetItem(format_preset["name"])
        )

    def remove_selected(self):
        selected_rows = set(item.row() for item in self.table_widget.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.queue.pop(row)
            self.table_widget.removeRow(row)

    def pop(self):
        if self.queue:
            self.table_widget.removeRow(0)
            return self.queue.pop(0)
        return None

    def is_empty(self):
        return len(self.queue) == 0

    def start_download(self):
        if not self.is_empty() and not self.worker:
            self.parent_obj.lock_ui()
            output_path = self.parent_obj.get_output_path()
            if output_path:
                format_preset = self.queue[0]["format_preset"]
                self.parent_obj.append_to_log(
                    f"Starting download with output path: {output_path}, Format Preset: {format_preset['name']}"
                )
                self.worker = DownloadWorker(
                    self, output_path, self.parent_obj.unlock_ui, format_preset
                )
                self.worker.progress_signal.connect(self.parent_obj.update_progress)
                self.worker.start()
            else:
                self.parent_obj.append_to_log("Please specify an output path.")
        elif self.worker:
            self.parent_obj.append_to_log("Download already in progress.")
        else:
            self.parent_obj.append_to_log("Queue is empty. Add videos to the queue.")


class VideoDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.queue_manager = QueueManager(parent_obj=self)
        self.custom_formats = []

        self.load_custom_formats()
        self.init_ui()

    def load_custom_formats(self):
        try:
            with open(CUSTOM_FORMAT_JSON_PATH, "r", encoding="utf-8") as file:
                self.custom_formats = json.load(file)
        except FileNotFoundError:
            self.save_custom_formats()

    def save_custom_formats(self):
        with open(CUSTOM_FORMAT_JSON_PATH, "w", encoding="utf-8") as file:
            json.dump(self.custom_formats, file, indent=2)

    def init_ui(self):
        self.load_custom_formats()  # Load custom formats on launch

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)

        left_layout = QVBoxLayout()

        self.url_label = QLabel("Video URL:")
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.add_button = QPushButton("Add to Queue", clicked=self.add_to_queue)

        left_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.add_button)
        left_layout.addLayout(url_layout)

        self.output_label = QLabel("Output Path:")
        output_layout = QHBoxLayout()
        self.output_path_input = QLineEdit()
        self.output_path_input.setText(os.getcwd())
        self.browse_button = QPushButton("Browse", clicked=self.browse_output_path)

        left_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_path_input)
        output_layout.addWidget(self.browse_button)
        left_layout.addLayout(output_layout)

        subs_layout = QHBoxLayout()
        self.download_subs_label = QLabel("Download Subtitles:")
        self.download_subs_checkbox = QComboBox()
        self.download_subs_checkbox.addItems(["True", "False"])
        self.subs_lang_label = QLabel("Subtitles Language:")
        self.subs_lang_combobox = QComboBox()
        self.subs_lang_combobox.addItems(["en", "es", "fr", "de", "it", "pt", "ru"])

        subs_layout.addWidget(self.download_subs_label)
        subs_layout.addWidget(self.download_subs_checkbox)
        subs_layout.addWidget(self.subs_lang_label)
        subs_layout.addWidget(self.subs_lang_combobox)
        left_layout.addLayout(subs_layout)

        formats_layout = QHBoxLayout()
        self.format_label = QLabel("Format Preset:")
        self.format_combobox = QComboBox()
        self.populate_format_combobox()

        formats_layout.addWidget(self.format_label)
        formats_layout.addWidget(self.format_combobox)
        left_layout.addLayout(formats_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output)

        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)
        self.progress_bar.setValue(0)

        layout.addLayout(left_layout)

        layout.addWidget(self.queue_manager)

    def populate_format_combobox(self):
        default_formats = [
            {
                "name": "Best Video + Audio (MP4)",
                "format": "best[ext=mp4]",
            },
            {
                "name": "Best Audio (MP3)",
                "format": "mp3/bestaudio/best",
                "postprocessor_args": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
                ],
            },
        ]
        for default_format in default_formats:
            self.format_combobox.addItem(
                default_format["name"], userData=default_format
            )

        if self.custom_formats:
            self.format_combobox.insertSeparator(len(default_formats))
            for custom_format in self.custom_formats:
                custom_format["name"] = f"{custom_format['name']} (Custom)"
                self.format_combobox.addItem(
                    custom_format["name"], userData=custom_format
                )

    def add_to_queue(self):
        url = self.url_input.text()
        if url:
            video_info = yt_dlp.YoutubeDL().extract_info(url, download=False)
            title = video_info.get("title", "Unknown Title")
            download_subs = self.download_subs_checkbox.currentText().lower() == "true"
            subs_lang = self.subs_lang_combobox.currentText()
            format_preset = self.format_combobox.currentData()
            self.queue_manager.add_video(
                title, url, download_subs, subs_lang, format_preset
            )
            self.log_output.append(f"Added to queue: {url}")
            self.url_input.clear()

    def update_progress(self, message, progress):
        if message:
            self.log_output.append(message)
        self.progress_bar.setValue(progress)

    def browse_output_path(self):
        output_path = QFileDialog.getExistingDirectory(self, "Select Output Path")
        if output_path:
            self.output_path_input.setText(output_path)

    def append_to_log(self, message):
        self.log_output.append(message)

    def get_output_path(self):
        return self.output_path_input.text()

    def lock_ui(self):
        self.url_input.setEnabled(False)
        self.add_button.setEnabled(False)
        self.output_path_input.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.download_subs_checkbox.setEnabled(False)
        self.subs_lang_combobox.setEnabled(False)
        self.queue_manager.remove_button.setEnabled(False)
        self.queue_manager.start_button.setEnabled(False)
        self.format_combobox.setEnabled(False)

    def unlock_ui(self):
        self.url_input.setEnabled(True)
        self.add_button.setEnabled(True)
        self.output_path_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.download_subs_checkbox.setEnabled(True)
        self.subs_lang_combobox.setEnabled(True)
        self.queue_manager.remove_button.setEnabled(True)
        self.queue_manager.start_button.setEnabled(True)
        self.format_combobox.setEnabled(True)
        self.queue_manager.worker.quit()
        self.queue_manager.worker = None

    def start_download(self):
        if not self.queue_manager.is_empty() and not self.queue_manager.worker:
            format_preset = self.format_combobox.currentData()
            self.queue_manager.start_download(format_preset)
        elif self.queue_manager.worker:
            self.append_to_log("Download already in progress.")
        else:
            self.append_to_log("Queue is empty. Add videos to the queue.")

    def load_custom_formats_ui(self):
        self.load_custom_formats()
        self.format_combobox.clear()
        self.populate_format_combobox()
        self.append_to_log("Custom formats loaded.")


def main():
    app = QApplication(sys.argv)
    window = VideoDownloaderApp()
    window.setWindowTitle("YouTube Downloader")
    window.resize(800, 400)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
