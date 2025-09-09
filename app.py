import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QCalendarWidget, QListWidget, QPushButton, QInputDialog, QMessageBox, QLabel, QSizePolicy,
    QDialog, QFormLayout, QLineEdit, QTimeEdit, QDialogButtonBox, QSpinBox, QComboBox, QTextEdit, QListWidgetItem, QTextBrowser, QToolButton
)
from PyQt5.QtCore import QDate, Qt, QRectF, QSize, QEvent
from PyQt5.QtGui import QFont, QPainter, QColor, QPainterPath, QTextOption, QPixmap, QPolygon, QIcon
from PyQt5.QtCore import QDate, Qt, QRectF, QSize, QEvent, QPoint
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import pickle
import datetime
import subprocess

SCOPES = ["https://www.googleapis.com/auth/calendar"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.pkl")
SHOW_HOLIDAYS = True
HOLIDAY_CALENDAR_IDS = [
    "ro.romanian#holiday@group.v.calendar.google.com",
    "ro.romanian@holiday.calendar.google.com",
    "en.romanian#holiday@group.v.calendar.google.com",
]

class Calendar(QCalendarWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.date_to_events = {}

    def paintCell(self, painter: QPainter, rect, date: QDate):
        super().paintCell(painter, rect, date)
        is_selected = (date == self.selectedDate())
        is_current_month = (date.month() == self.monthShown() and date.year() == self.yearShown())
        if not is_selected:
            painter.save()
            if is_current_month:
                painter.fillRect(rect, QColor(0, 0, 0, 40))
            else:
                painter.fillRect(rect, QColor(0, 0, 0, 90))
            painter.restore()

        # Render event titles (first 2) inside the cell for current month
        if is_current_month and date in self.date_to_events:
            events = self.date_to_events.get(date, [])[:2]
            if events:
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, True)
                y = rect.top() + 18
                for title, color_hex in events:
                    pill_rect = rect.adjusted(8, y - rect.top(), -8, 0)
                    pill_rect.setHeight(18)
                    painter.setBrush(QColor(color_hex))
                    painter.setPen(Qt.NoPen)
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(pill_rect), 9.0, 9.0)
                    painter.drawPath(path)
                    painter.setPen(QColor("#0b1a10"))
                    elided = title[:22] + ("…" if len(title) > 22 else "")
                    painter.drawText(pill_rect.adjusted(6, 0, -6, 0), 0x84, elided)
                    y += 18
                painter.restore()

    def set_events_for_month(self, mapping):
        self.date_to_events = mapping or {}
        self.updateCells()


class AddEventDialog(QDialog):
    def __init__(self, parent=None, default_date: QDate = None):
        super().__init__(parent)
        self.setWindowTitle("Adaugă eveniment")
        layout = QFormLayout(self)
        self.title_edit = QLineEdit(self)
        self.start_time = QTimeEdit(self)
        self.end_time = QTimeEdit(self)
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time.setDisplayFormat("HH:mm")
        self.reminder_minutes = QSpinBox(self)
        self.reminder_minutes.setRange(0, 1440)
        self.reminder_minutes.setSuffix(" min")
        self.reminder_minutes.setValue(30)
        self.description_edit = QTextEdit(self)
        self.description_edit.setMinimumHeight(100)
        self.color_combo = QComboBox(self)
        self.color_options = [
            ("Rosu", "#d32f2f", 11),
            ("Portocaliu", "#f57c00", 6),
            ("Galben", "#fbc02d", 5),
            ("Verde", "#388e3c", 10),
            ("Turcoaz", "#00897b", 9),
            ("Albastru", "#1976d2", 1),
            ("Mov", "#7b1fa2", 3),
            ("Gri", "#757575", 8)
        ]
        for name, color, _ in self.color_options:
            self.color_combo.addItem(name)

        layout.addRow("Titlu", self.title_edit)
        layout.addRow("Începe la", self.start_time)
        layout.addRow("Se termină la", self.end_time)
        layout.addRow("Notificare", self.reminder_minutes)
        layout.addRow("Descriere", self.description_edit)
        layout.addRow("Culoare", self.color_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self):
        idx = self.color_combo.currentIndex()
        _, color_hex, color_id = self.color_options[idx]
        return (
            self.title_edit.text().strip(),
            self.start_time.time(),
            self.end_time.time(),
            int(self.reminder_minutes.value()),
            color_hex,
            color_id,
            self.description_edit.toPlainText().strip(),
        )


class CalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Calendar")
        self.resize(950, 550)

        self.service = self.get_calendar_service()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.calendar = Calendar()
        self.calendar.selectionChanged.connect(self.load_events)
        self.calendar.setGridVisible(True)
        self.calendar.setFont(QFont("Segoe UI", 11))
        self.calendar.currentPageChanged.connect(self.refresh_month_events)

        right_layout = QVBoxLayout()

        title = QLabel("📅 Evenimente")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))

        self.events_list = QListWidget()
        self.events_list.setFont(QFont("Segoe UI", 10))
        self.events_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.events_list.setWordWrap(True)
        from PyQt5.QtCore import Qt as _Qt
        self.events_list.setHorizontalScrollBarPolicy(_Qt.ScrollBarAlwaysOff)
        self.events_list.setTextElideMode(_Qt.ElideNone)
        self.events_list.itemClicked.connect(self._toggle_event_description)
        self._widget_to_item = {}

        self.add_button = QPushButton("➕ Adaugă Eveniment")
        self.add_button.clicked.connect(self.add_event)
        self.edit_button = QPushButton("✏️ Editează Ev.")
        self.edit_button.setFixedWidth(120)
        self.edit_button.clicked.connect(self.edit_event)
        self.edit_button.setObjectName("edit")

        bottom_buttons = QHBoxLayout()
        self.delete_button = QPushButton("🗑️ Șterge Eveniment")
        self.delete_button.clicked.connect(self.delete_event)
        self.logout_button = QPushButton("🚪 Delogare")
        self.logout_button.setFixedWidth(120)
        self.logout_button.clicked.connect(self.logout)

        bottom_buttons.addWidget(self.delete_button, stretch=2)
        bottom_buttons.addWidget(self.logout_button, stretch=1)

        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(title)
        right_layout.addWidget(self.events_list)
        buttons_row = QHBoxLayout()
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.edit_button)
        right_layout.addLayout(buttons_row)
        right_layout.addLayout(bottom_buttons)

        main_layout.addWidget(self.calendar, 2)
        main_layout.addLayout(right_layout, 1)

        self.load_events()
        self.refresh_month_events()

        QApplication.instance().setStyleSheet("""
            QMainWindow {
                background-color: #121212;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QDialog, QMessageBox, QInputDialog {
                background-color: #121212;
                color: #ffffff;
            }
            QLineEdit, QTimeEdit, QSpinBox, QComboBox, QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #3a3a3a;
            }
            QCalendarWidget {
                border: 1px solid #333;
                border-radius: 10px;
                background: #1e1e1e;
                color: #ffffff;
                font-size: 14px;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #1e1e1e;
                selection-background-color: #3a3a3a;
                selection-color: #ffffff;
                color: #ffffff;
                gridline-color: #2E2E2E;
            }
            QCalendarWidget QAbstractItemView::item:enabled {
                background-color: #1f1f1f;
            }
            QCalendarWidget QAbstractItemView::item:disabled {
                background-color: #0f0f0f;
                color: #777777;
            }
            QCalendarWidget QWidget { 
                alternate-background-color: #1F1F1F;
                background-color: #141414;
                color: #ffffff;
            }
            QListWidget {
                border: 1px solid #333;
                border-radius: 8px;
                padding: 6px;
                background: #1e1e1e;
                color: #ffffff;
            }
            QListWidget::item {
                border-bottom: 1px solid #333;
                padding: 8px 6px;
            }
            QToolButton#expand {
                color: #cccccc;
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 0px;
                min-width: 24px;
                qproperty-iconSize: 12px;
            }
            QToolButton#expand:hover { color: #ffffff; background-color: #3a3a3a; }
            QPushButton {
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                color: #fff;
            }
            QPushButton:hover {
                opacity: 0.85;
            }
            QPushButton:pressed {
                opacity: 0.7;
            }
            QPushButton#add {
                background-color: #4caf50;
            }
            QPushButton#delete {
                background-color: #e53935;
            }
            QPushButton#logout {
                background-color: #757575;
            }
            QPushButton#edit {
                background-color: #4169E1;
            }
        """)

        self.add_button.setObjectName("add")
        self.delete_button.setObjectName("delete")
        self.logout_button.setObjectName("logout")

    @staticmethod
    def to_local_rfc3339(dt_naive: datetime.datetime) -> str:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        return dt_naive.replace(tzinfo=local_tz).isoformat()

    @staticmethod
    def format_event_label(event, color_hex: str) -> str:
        title = event.get('summary', 'Fără titlu')
        start_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        display_time = ""
        try:
            if "T" in start_str:
                dt = datetime.datetime.fromisoformat(start_str)
                dt_local = dt.astimezone()
                display_time = dt_local.strftime("%Y-%m-%d %H:%M")
            else:
                display_time = start_str
        except Exception:
            display_time = start_str or ""
        dot = f"<span style='color:{color_hex};'>●</span>"
        return f"{dot} {display_time} - {title}"

    def _add_event_list_item(self, event):
        desc = (event.get("description", "") or "").strip()
        color_hex = self.google_color_id_to_hex(event.get("colorId"))

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        toggle_btn = QToolButton()
        toggle_btn.setFixedSize(24, 24)
        toggle_btn.setObjectName("expand")
        toggle_btn.setAutoRaise(True)
        # Set a smaller custom chevron icon
        pm = QPixmap(12, 12)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#d0d0d0'))
        poly = QPolygon([
            QPoint(4, 2), QPoint(9, 6), QPoint(4, 10)
        ])
        painter.drawPolygon(poly)
        painter.end()
        toggle_btn.setIcon(QIcon(pm))
        toggle_btn.setIconSize(QSize(12, 12))
        title_lbl = QLabel(self.format_event_label(event, color_hex))
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setWordWrap(True)
        title_lbl.setMargin(2)
        title_lbl.setMinimumHeight(title_lbl.fontMetrics().height() + 6)
        header.addWidget(title_lbl, 1)
        header.addStretch(1)
        header.addWidget(toggle_btn)
        desc_view = QTextBrowser()
        desc_view.setText(desc if desc else "(fără descriere)")
        desc_view.setOpenExternalLinks(True)
        desc_view.setReadOnly(True)
        desc_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        desc_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapAnywhere)
        desc_view.document().setDefaultTextOption(opt)
        desc_view.setStyleSheet("QTextBrowser{background:transparent;border:none;color:#ffffff;}")
        desc_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        desc_view.setVisible(False)
        desc_view.setObjectName("desc")

        v.addLayout(header)
        v.addWidget(desc_view)

        item = QListWidgetItem()
        container.adjustSize()
        item.setSizeHint(container.sizeHint() + QSize(0, 4))
        self.events_list.addItem(item)
        self.events_list.setItemWidget(item, container)
        container.installEventFilter(self)
        self._widget_to_item[container] = item
        toggle_btn.clicked.connect(lambda: self._toggle_by_container(container, toggle_btn))

    def _toggle_event_description(self, item):
        container = self.events_list.itemWidget(item)
        if container is None:
            return
        desc_view = container.findChild(QTextBrowser, "desc")
        if desc_view is None:
            return
        new_state = not desc_view.isVisible()
        desc_view.setVisible(new_state)
        if new_state:
            desc_view.document().adjustSize()
            h = int(desc_view.document().size().height()) + 8
            if h < 20:
                h = 20
            desc_view.setFixedHeight(h)
        else:
            desc_view.setFixedHeight(0)
        container.adjustSize()
        item.setSizeHint(container.sizeHint() + QSize(0, 12))
        self.events_list.doItemsLayout()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.MouseButtonRelease and watched in self._widget_to_item:
            item = self._widget_to_item.get(watched)
            if item is not None:
                self._toggle_event_description(item)
                return True
        return super().eventFilter(watched, event)

    def _toggle_by_container(self, container, btn=None):
        item = self._widget_to_item.get(container)
        if item is None:
            return
        self._toggle_event_description(item)
        if btn is not None:
            desc_view = container.findChild(QTextBrowser, "desc")
            # Flip icon by rotating 90 degrees when expanded
            size = 12
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#d0d0d0'))
            if desc_view and desc_view.isVisible():
                poly = QPolygon([QPoint(2, 4), QPoint(6, 9), QPoint(10, 4)])
            else:
                poly = QPolygon([QPoint(4, 2), QPoint(9, 6), QPoint(4, 10)])
            painter.drawPolygon(poly)
            painter.end()
            btn.setIcon(QIcon(pm))

    def get_calendar_service(self):
        creds = None
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, "wb") as token:
                pickle.dump(creds, token)
        return build("calendar", "v3", credentials=creds)

    def load_events(self):
        self.events_list.clear()
        date = self.calendar.selectedDate()
        start = datetime.datetime(date.year(), date.month(), date.day(), 0, 0, 0)
        end = start + datetime.timedelta(days=1)

        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=self.to_local_rfc3339(start),
            timeMax=self.to_local_rfc3339(end),
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        self.events = events_result.get("items", [])
        for event in self.events:
            self._add_event_list_item(event)

    def refresh_month_events(self):
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        first = datetime.datetime(year, month, 1, 0, 0, 0)
        if month == 12:
            next_month = datetime.datetime(year + 1, 1, 1)
        else:
            next_month = datetime.datetime(year, month + 1, 1)
        mapping = {}
        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=self.to_local_rfc3339(first),
            timeMax=self.to_local_rfc3339(next_month),
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        items = events_result.get("items", [])
        for ev in items:
            start_str = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            try:
                date_part = start_str.split("T")[0]
                y, m, d = [int(x) for x in date_part.split("-")]
                qd = QDate(y, m, d)
                color_hex = self.google_color_id_to_hex(ev.get("colorId"))
                mapping.setdefault(qd, []).append((ev.get("summary", "Fără titlu"), color_hex))
            except Exception:
                continue

        if SHOW_HOLIDAYS:
            for cal_id in HOLIDAY_CALENDAR_IDS:
                try:
                    hol = self.service.events().list(
                        calendarId=cal_id,
                        timeMin=self.to_local_rfc3339(first),
                        timeMax=self.to_local_rfc3339(next_month),
                        singleEvents=True,
                        orderBy="startTime"
                    ).execute()
                    hol_items = hol.get("items", [])
                    for ev in hol_items:
                        start_str = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
                        try:
                            date_part = start_str.split("T")[0]
                            y, m, d = [int(x) for x in date_part.split("-")]
                            qd = QDate(y, m, d)
                            mapping.setdefault(qd, []).append((ev.get("summary", "Sărbătoare"), "#4caf50"))
                        except Exception:
                            continue
                    break
                except Exception:
                    continue
        self.calendar.set_events_for_month(mapping)

    @staticmethod
    def google_color_id_to_hex(color_id):
        palette = {
            "1": "#a4bdfc", "2": "#7ae7bf", "3": "#dbadff", "4": "#ff887c",
            "5": "#fbd75b", "6": "#ffb878", "7": "#46d6db", "8": "#e1e1e1",
            "9": "#5484ed", "10": "#51b749", "11": "#dc2127"
        }
        return palette.get(str(color_id), "#51b749")

    def add_event(self):
        dlg = AddEventDialog(self, self.calendar.selectedDate())
        if dlg.exec_() == QDialog.Accepted:
            title, qstart, qend, reminder_min, color_hex, color_id, description = dlg.get_values()
            if not title:
                return
            date = self.calendar.selectedDate()
            start = datetime.datetime(date.year(), date.month(), date.day(), qstart.hour(), qstart.minute(), 0)
            end = datetime.datetime(date.year(), date.month(), date.day(), qend.hour(), qend.minute(), 0)
            if end <= start:
                end = start + datetime.timedelta(hours=1)

            event = {
                "summary": title,
                "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Bucharest"},
                "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Bucharest"},
                "colorId": str(color_id),
                "description": description,
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": reminder_min}] if reminder_min > 0 else []
                }
            }
            self.service.events().insert(calendarId="primary", body=event).execute()
            self.load_events()
            self.refresh_month_events()

    def delete_event(self):
        selected = self.events_list.currentRow()
        if selected >= 0:
            event = self.events[selected]
            reply = QMessageBox.question(
                self, "Confirmare", f"Ștergi evenimentul '{event.get('summary', 'Fără titlu')}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.service.events().delete(calendarId="primary", eventId=event["id"]).execute()
                self.load_events()
                self.refresh_month_events()

    def edit_event(self):
        selected = self.events_list.currentRow()
        if selected < 0:
            return
        ev = self.events[selected]
        dlg = AddEventDialog(self, self.calendar.selectedDate())
        dlg.title_edit.setText(ev.get("summary", ""))
        # Set times if present
        start_str = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end_str = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")
        try:
            if start_str and "T" in start_str:
                h, m = start_str.split("T")[1][:5].split(":")
                from PyQt5.QtCore import QTime
                dlg.start_time.setTime(QTime(int(h), int(m)))
            if end_str and "T" in end_str:
                h, m = end_str.split("T")[1][:5].split(":")
                from PyQt5.QtCore import QTime
                dlg.end_time.setTime(QTime(int(h), int(m)))
        except Exception:
            pass
        dlg.description_edit.setText(ev.get("description", ""))
        if dlg.exec_() == QDialog.Accepted:
            title, qstart, qend, reminder_min, color_hex, color_id, description = dlg.get_values()
            date = self.calendar.selectedDate()
            start = datetime.datetime(date.year(), date.month(), date.day(), qstart.hour(), qstart.minute(), 0)
            end = datetime.datetime(date.year(), date.month(), date.day(), qend.hour(), qend.minute(), 0)
            if end <= start:
                end = start + datetime.timedelta(hours=1)
            body = {
                "summary": title,
                "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Bucharest"},
                "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Bucharest"},
                "description": description,
                "colorId": str(color_id),
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": reminder_min}] if reminder_min > 0 else []
                }
            }
            self.service.events().patch(calendarId="primary", eventId=ev["id"], body=body).execute()
            self.load_events()
            self.refresh_month_events()

    def logout(self):
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        QMessageBox.information(self, "Logout", "Ai fost delogat. Se va reporni aplicația.")
        python = sys.executable
        os.execl(python, python, *sys.argv)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CalendarApp()
    window.show()
    sys.exit(app.exec_())