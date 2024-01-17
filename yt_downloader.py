import sys
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
import os
import math


class DownloadWorker(QThread):
    progress_signal = Signal(str, int)

    def __init__(self, queue_manager, output_path, on_finish):
        super().__init__()
        self.queue_manager = queue_manager
        self.output_path = output_path
        self.on_finish = on_finish

    def run(self):
        ydl_opts = {
            "format": "bestvideo[height<=1080][ext=mp4]",
            "outtmpl": os.path.join(self.output_path, "%(title)s.%(ext)s"),
            "progress_hooks": [self.progress_hook],
            "writesubtitles": True,
            "subtitleslangs": [],
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
    def __init__(self, parent_obj=None):
        super().__init__()

        self.queue = []
        self.worker = None
        self.parent_obj = parent_obj
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(
            ["Title", "URL", "Download Subs", "Subs Language"]
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

    def add_video(self, title, url, download_subs, subs_lang):
        self.queue.append(
            {
                "title": title,
                "url": url,
                "download_subs": download_subs,
                "subs_lang": subs_lang,
            }
        )
        row_position = self.table_widget.rowCount()
        self.table_widget.insertRow(row_position)
        self.table_widget.setItem(row_position, 0, QTableWidgetItem(title))
        self.table_widget.setItem(row_position, 1, QTableWidgetItem(url))
        self.table_widget.setItem(row_position, 2, QTableWidgetItem(str(download_subs)))
        self.table_widget.setItem(row_position, 3, QTableWidgetItem(subs_lang))

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
                self.parent_obj.append_to_log(
                    f"Starting download with output path: {output_path}"
                )
                self.worker = DownloadWorker(
                    self, output_path, self.parent_obj.unlock_ui
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

        self.init_ui()

    def init_ui(self):
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

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output)

        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)
        self.progress_bar.setValue(0)

        layout.addLayout(left_layout)

        layout.addWidget(self.queue_manager)

    def add_to_queue(self):
        url = self.url_input.text()
        if url:
            video_info = yt_dlp.YoutubeDL().extract_info(url, download=False)
            title = video_info.get("title", "Unknown Title")
            download_subs = self.download_subs_checkbox.currentText().lower() == "true"
            subs_lang = self.subs_lang_combobox.currentText()
            self.queue_manager.add_video(title, url, download_subs, subs_lang)
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

    def unlock_ui(self):
        self.url_input.setEnabled(True)
        self.add_button.setEnabled(True)
        self.output_path_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.download_subs_checkbox.setEnabled(True)
        self.subs_lang_combobox.setEnabled(True)
        self.queue_manager.remove_button.setEnabled(True)
        self.queue_manager.start_button.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = VideoDownloaderApp()
    window.setWindowTitle("YouTube Downloader")
    window.resize(800, 400)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
