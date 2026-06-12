"""
BWS Tracker v1.0  —  Mobile Application
Kivy-based Water Gallon Delivery Tracker
Android & iOS compatible
"""

# ── Standard library ──────────────────────────────────────────────────────────
import os
import csv
import sqlite3
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional, List

# ── Kivy window config (must be before other kivy imports) ────────────────────
from kivy.config import Config
Config.set('graphics', 'resizable', '1')

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.clock import Clock

# Push view above keyboard on mobile
Window.softinput_mode = 'below_target'

# ── ReportLab (optional) ──────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

VALID_GALLON_TYPES  = ["Round", "Slim", "Both"]
C_BLUE              = (0.169, 0.424, 0.690, 1)
C_BLUE_DARK         = (0.118, 0.310, 0.529, 1)
C_BLUE_LIGHT        = (0.922, 0.957, 1.000, 1)
C_WHITE             = (1.000, 1.000, 1.000, 1)
C_BG                = (0.969, 0.980, 0.988, 1)
C_TEXT              = (0.102, 0.125, 0.173, 1)
C_MUTED             = (0.443, 0.502, 0.588, 1)
C_BORDER            = (0.796, 0.835, 0.878, 1)
C_RED               = (0.773, 0.188, 0.188, 1)
C_GREEN             = (0.153, 0.533, 0.329, 1)
C_YELLOW_BG         = (0.996, 0.953, 0.780, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._bootstrap()

    def _bootstrap(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id   INTEGER NOT NULL REFERENCES customers(id),
                gallon_type   TEXT    NOT NULL CHECK(gallon_type IN ('Round','Slim','Both')),
                is_refill     INTEGER NOT NULL,
                water_price   REAL    NOT NULL DEFAULT 0.0,
                deposit_fee   REAL    NOT NULL DEFAULT 0.0,
                delivery_time TEXT,
                order_date    TEXT    NOT NULL
            );
        """)
        self.conn.commit()

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
#  DOMAIN MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Customer:
    id:   Optional[int]
    name: str


@dataclass
class Order:
    id:            Optional[int]
    customer_id:   int
    gallon_type:   str
    is_refill:     bool
    water_price:   float = 0.0
    deposit_fee:   float = 0.0
    delivery_time: str   = "Not Specified"
    order_date:    str   = field(default_factory=lambda: datetime.now().isoformat())
    customer_name: str   = ""

    @property
    def total_amount(self) -> float:
        return self.water_price + self.deposit_fee

    @property
    def service_label(self) -> str:
        return "Refill" if self.is_refill else "Borrow"

    @property
    def date_only(self) -> str:
        return self.order_date[:10]

    @classmethod
    def create(cls, customer_id, gallon_type, is_refill,
               water_price=0.0, deposit_fee=0.0, delivery_time="") -> "Order":
        if gallon_type not in VALID_GALLON_TYPES:
            raise ValueError(f"Invalid gallon type: {gallon_type}")
        resolved_deposit = 0.0 if is_refill else deposit_fee
        resolved_time    = delivery_time.strip() or "Not Specified"
        return cls(
            id=None,
            customer_id=customer_id,
            gallon_type=gallon_type,
            is_refill=is_refill,
            water_price=water_price,
            deposit_fee=resolved_deposit,
            delivery_time=resolved_time,
            order_date=datetime.now().isoformat(),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  REPOSITORIES
# ══════════════════════════════════════════════════════════════════════════════

class CustomerRepository:
    def __init__(self, db: Database):
        self.db = db

    def find_by_name(self, name: str) -> Optional[Customer]:
        row = self.db.execute(
            "SELECT id, name FROM customers WHERE name = ?", (name.strip(),)
        ).fetchone()
        return Customer(id=row["id"], name=row["name"]) if row else None

    def get_or_create(self, name: str):
        existing = self.find_by_name(name)
        if existing:
            return existing, False
        cur = self.db.execute("INSERT INTO customers (name) VALUES (?)", (name.strip(),))
        self.db.commit()
        return Customer(id=cur.lastrowid, name=name.strip()), True

    def all(self) -> List[Customer]:
        rows = self.db.execute(
            "SELECT id, name FROM customers ORDER BY name"
        ).fetchall()
        return [Customer(id=r["id"], name=r["name"]) for r in rows]


class OrderRepository:
    def __init__(self, db: Database):
        self.db = db

    def save(self, order: Order) -> Order:
        cur = self.db.execute(
            """INSERT INTO orders
               (customer_id, gallon_type, is_refill, water_price,
                deposit_fee, delivery_time, order_date)
               VALUES (?,?,?,?,?,?,?)""",
            (order.customer_id, order.gallon_type, int(order.is_refill),
             order.water_price, order.deposit_fee, order.delivery_time, order.order_date),
        )
        self.db.commit()
        order.id = cur.lastrowid
        return order

    def find_by_date(self, target_date: str) -> List[Order]:
        rows = self.db.execute(
            """SELECT o.*, c.name AS customer_name
               FROM orders o JOIN customers c ON c.id = o.customer_id
               WHERE o.order_date LIKE ? ORDER BY o.order_date""",
            (f"{target_date}%",),
        ).fetchall()
        return [self._hydrate(r) for r in rows]

    def all_with_customer(self) -> List[Order]:
        rows = self.db.execute(
            """SELECT o.*, c.name AS customer_name
               FROM orders o JOIN customers c ON c.id = o.customer_id
               ORDER BY o.order_date DESC"""
        ).fetchall()
        return [self._hydrate(r) for r in rows]

    @staticmethod
    def _hydrate(row) -> Order:
        return Order(
            id=row["id"], customer_id=row["customer_id"],
            gallon_type=row["gallon_type"], is_refill=bool(row["is_refill"]),
            water_price=row["water_price"], deposit_fee=row["deposit_fee"],
            delivery_time=row["delivery_time"] or "Not Specified",
            order_date=row["order_date"], customer_name=row["customer_name"],
        )


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DailyMetrics:
    target_date:       str
    order_count:       int
    gross_water_sales: float
    total_deposits:    float
    combined_inflow:   float

    @classmethod
    def compute(cls, orders: List[Order], target_date: str) -> "DailyMetrics":
        return cls(
            target_date=target_date,
            order_count=len(orders),
            gross_water_sales=sum(o.water_price  for o in orders),
            total_deposits=   sum(o.deposit_fee  for o in orders),
            combined_inflow=  sum(o.total_amount for o in orders),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  EXPORT PIPELINES
# ══════════════════════════════════════════════════════════════════════════════

class CSVExporter:
    HEADERS = ["ID", "Customer", "Gallon", "Service", "Water Price",
               "Deposit", "Total", "Time"]

    @staticmethod
    def export(orders: List[Order], target_date: str, path: str) -> str:
        m = DailyMetrics.compute(orders, target_date)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSVExporter.HEADERS)
            for o in orders:
                w.writerow([o.id, o.customer_name, o.gallon_type,
                            o.service_label, f"{o.water_price:.2f}",
                            f"{o.deposit_fee:.2f}", f"{o.total_amount:.2f}",
                            o.delivery_time])
            w.writerow([])
            w.writerow(["TOTALS", f"{m.order_count} orders", "", "",
                        f"{m.gross_water_sales:.2f}", f"{m.total_deposits:.2f}",
                        f"{m.combined_inflow:.2f}", ""])
        return path


class PDFExporter:
    @staticmethod
    def export(orders: List[Order], target_date: str, path: str) -> str:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab not available.")

        m   = DailyMetrics.compute(orders, target_date)
        doc = SimpleDocTemplate(path, pagesize=A4,
                                leftMargin=18*mm, rightMargin=18*mm,
                                topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        story  = []

        BLUE       = rl_colors.HexColor("#2B6CB0")
        BLUE_LIGHT = rl_colors.HexColor("#EBF4FF")
        YELLOW     = rl_colors.HexColor("#FEF3C7")
        GRAY_ROW   = rl_colors.HexColor("#F9FAFB")
        GRAY_LINE  = rl_colors.HexColor("#D1D5DB")

        def ps(name, **kw):
            return ParagraphStyle(name, fontName="Helvetica", **kw)

        # Header banner
        hdr_data = [[
            Paragraph(f'<font color="white" size="15"><b>BWS TRACKER LEDGER</b></font>',
                      ps("h1", textColor=rl_colors.white, alignment=TA_LEFT)),
            Paragraph(
                f'<font color="white" size="8">Date: {target_date}<br/>'
                f'Orders: {m.order_count}<br/>'
                f'Printed: {datetime.now().strftime("%Y-%m-%d %H:%M")}</font>',
                ps("h2", textColor=rl_colors.white, alignment=TA_RIGHT)),
        ]]
        hdr_tbl = Table(hdr_data, colWidths=["65%", "35%"])
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), BLUE),
            ("TOPPADDING",   (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 14),
            ("LEFTPADDING",  (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(hdr_tbl)
        story.append(Spacer(1, 7*mm))

        # Metrics strip
        def mcell(lbl, val):
            return Paragraph(
                f'<font size="7" color="#6B7280">{lbl}</font><br/>'
                f'<font size="12"><b>&#8369; {val:,.2f}</b></font>',
                ps("mc", fontSize=12, leading=18, alignment=TA_CENTER))

        mdata = [[mcell("Gross Water Sales", m.gross_water_sales),
                  mcell("Container Deposits", m.total_deposits),
                  mcell("Combined Cash Inflow", m.combined_inflow)]]
        mtbl = Table(mdata, colWidths=["33%", "33%", "34%"])
        mtbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), BLUE_LIGHT),
            ("BOX",          (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#BFDBFE")),
            ("INNERGRID",    (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#BFDBFE")),
            ("TOPPADDING",   (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(mtbl)
        story.append(Spacer(1, 7*mm))

        # Orders table
        heads = ["#", "Customer", "Gallon", "Service",
                 "Water ₱", "Deposit ₱", "Total ₱", "Time"]
        tdata = [heads]
        for o in orders:
            tdata.append([str(o.id), o.customer_name, o.gallon_type,
                          o.service_label,
                          f"₱{o.water_price:,.2f}", f"₱{o.deposit_fee:,.2f}",
                          f"₱{o.total_amount:,.2f}", o.delivery_time])
        tot_idx = len(tdata)
        tdata.append(["", Paragraph("<b>TOTALS</b>", ps("tb", fontName="Helvetica-Bold", fontSize=9)),
                      "", "",
                      Paragraph(f"<b>₱{m.gross_water_sales:,.2f}</b>",
                                ps("tv", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT)),
                      Paragraph(f"<b>₱{m.total_deposits:,.2f}</b>",
                                ps("tv2", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT)),
                      Paragraph(f"<b>₱{m.combined_inflow:,.2f}</b>",
                                ps("tv3", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT)),
                      ""])

        cw = [w*mm for w in [16, 78, 36, 36, 50, 52, 50, 58]]
        otbl = Table(tdata, colWidths=cw, repeatRows=1)
        style = [
            ("BACKGROUND",   (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR",    (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 8),
            ("TOPPADDING",   (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING",(0, 0), (-1, 0), 8),
            ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME",     (0, 1), (-1, tot_idx-1), "Helvetica"),
            ("FONTSIZE",     (0, 1), (-1, tot_idx-1), 8),
            ("ALIGN",        (0, 1), (-1, tot_idx-1), "CENTER"),
            ("ALIGN",        (1, 1), (1, tot_idx-1), "LEFT"),
            ("ALIGN",        (7, 1), (7, tot_idx-1), "LEFT"),
            ("TOPPADDING",   (0, 1), (-1, tot_idx-1), 6),
            ("BOTTOMPADDING",(0, 1), (-1, tot_idx-1), 6),
            ("BACKGROUND",   (0, tot_idx), (-1, tot_idx), YELLOW),
            ("FONTNAME",     (0, tot_idx), (-1, tot_idx), "Helvetica-Bold"),
            ("TOPPADDING",   (0, tot_idx), (-1, tot_idx), 8),
            ("BOTTOMPADDING",(0, tot_idx), (-1, tot_idx), 8),
            ("GRID",         (0, 0), (-1, -1), 0.4, GRAY_LINE),
            ("BOX",          (0, 0), (-1, -1), 1.0, BLUE),
            *[("BACKGROUND", (0, i), (-1, i), GRAY_ROW)
              for i in range(2, tot_idx, 2)],
        ]
        otbl.setStyle(TableStyle(style))
        story.append(otbl)
        story.append(Spacer(1, 6*mm))

        footer_ps = ps("ft", fontSize=7,
                       textColor=rl_colors.HexColor("#9CA3AF"), alignment=TA_CENTER)
        story.append(Paragraph(
            f"BWS Tracker  •  Report: {target_date}  •  "
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            footer_ps))
        doc.build(story)
        return path


# ══════════════════════════════════════════════════════════════════════════════
#  SEED DATA
# ══════════════════════════════════════════════════════════════════════════════

def seed_database(db, cust_repo, order_repo):
    if db.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        return
    samples = [
        ("Maria Santos",   "Round", False, 45.0, 100.0, "08:00 AM"),
        ("Juan dela Cruz", "Slim",  True,  40.0, 0.0,   "09:30 AM"),
        ("Ana Reyes",      "Both",  False, 80.0, 200.0, "10:15 AM"),
        ("Pedro Lim",      "Round", True,  45.0, 0.0,   "11:00 AM"),
        ("Rosa Garcia",    "Slim",  False, 40.0, 100.0, ""),
        ("Maria Santos",   "Round", False, 45.0, 100.0, "02:00 PM"),
    ]
    for name, gtype, refill, wp, dep, dtime in samples:
        customer, _ = cust_repo.get_or_create(name)
        order = Order.create(customer_id=customer.id, gallon_type=gtype,
                             is_refill=refill, water_price=wp,
                             deposit_fee=dep, delivery_time=dtime)
        order_repo.save(order)


# ══════════════════════════════════════════════════════════════════════════════
#  KV LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

KV = """
#:import dp kivy.metrics.dp

# ── Reusable widget rules ─────────────────────────────────────────────────────

<BWSButton@Button>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    color: 1, 1, 1, 1
    font_size: '16sp'
    bold: True
    size_hint_y: None
    height: '52dp'
    canvas.before:
        Color:
            rgba: (0.118, 0.310, 0.529, 1) if self.state == 'down' else (0.169, 0.424, 0.690, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<BWSOutlineButton@Button>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    color: 0.169, 0.424, 0.690, 1
    font_size: '15sp'
    bold: True
    size_hint_y: None
    height: '52dp'
    canvas.before:
        Color:
            rgba: (0.796, 0.878, 0.957, 1) if self.state == 'down' else (0.922, 0.957, 1.0, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: 0.169, 0.424, 0.690, 1
        Line:
            rounded_rectangle: (self.x+1, self.y+1, self.width-2, self.height-2, dp(10))
            width: 1.5

<BWSInput@TextInput>:
    background_color: 1, 1, 1, 1
    foreground_color: 0.102, 0.125, 0.173, 1
    cursor_color: 0.169, 0.424, 0.690, 1
    hint_text_color: 0.630, 0.680, 0.740, 1
    font_size: '15sp'
    size_hint_y: None
    height: '48dp'
    multiline: False
    padding: [14, 14, 14, 14]
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
        Color:
            rgba: (0.169, 0.424, 0.690, 0.8) if self.focus else (0.796, 0.835, 0.878, 1)
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
            width: 1.5 if self.focus else 1

<SectionLabel@Label>:
    color: 0.443, 0.502, 0.588, 1
    font_size: '11sp'
    bold: True
    size_hint_y: None
    height: '22dp'
    text_size: self.width, None
    halign: 'left'

# ── Screen: Home ──────────────────────────────────────────────────────────────

<HomeScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        # Header
        BoxLayout:
            size_hint_y: None
            height: '100dp'
            padding: ['24dp', '20dp', '24dp', '16dp']
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            BoxLayout:
                orientation: 'vertical'
                spacing: '4dp'
                Label:
                    text: 'BWS TRACKER'
                    color: 1, 1, 1, 1
                    font_size: '24sp'
                    bold: True
                    halign: 'left'
                    text_size: self.width, None
                Label:
                    text: 'Water Gallon Delivery Manager'
                    color: 0.700, 0.860, 1.000, 1
                    font_size: '13sp'
                    halign: 'left'
                    text_size: self.width, None

        # Today summary bar
        BoxLayout:
            id: today_bar
            size_hint_y: None
            height: '48dp'
            padding: ['24dp', '0dp']
            canvas.before:
                Color:
                    rgba: 0.922, 0.957, 1.0, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                id: today_label
                text: ''
                color: 0.169, 0.424, 0.690, 1
                font_size: '13sp'
                halign: 'left'
                text_size: self.width, None

        # Menu buttons
        ScrollView:
            GridLayout:
                cols: 1
                spacing: '12dp'
                padding: ['24dp', '24dp', '24dp', '24dp']
                size_hint_y: None
                height: self.minimum_height

                BWSButton:
                    text: '+ Add New Order'
                    on_release: app.go_to('add_order')

                BWSOutlineButton:
                    text: 'View Orders by Date'
                    on_release: app.go_to('view_orders')

                BWSOutlineButton:
                    text: 'Daily Metrics / Analytics'
                    on_release: app.go_to('metrics')

                BWSOutlineButton:
                    text: 'Export Reports  (CSV / PDF)'
                    on_release: app.go_to('export')

                BWSOutlineButton:
                    text: 'Customer List'
                    on_release: app.go_to('customers')

        Widget:

        # Footer
        Label:
            size_hint_y: None
            height: '36dp'
            text: 'BWS Tracker v1.0  —  Water Gallon Delivery'
            color: 0.630, 0.680, 0.740, 1
            font_size: '11sp'

# ── Screen: Add Order ─────────────────────────────────────────────────────────

<AddOrderScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        # Header
        BoxLayout:
            size_hint_y: None
            height: '64dp'
            padding: ['16dp', '12dp']
            spacing: '12dp'
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: '<'
                size_hint_x: None
                width: '44dp'
                background_color: 0, 0, 0, 0
                color: 1, 1, 1, 1
                font_size: '22sp'
                bold: True
                on_release: app.go_back()
            Label:
                text: 'Add New Order'
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                halign: 'left'
                text_size: self.width, None

        ScrollView:
            GridLayout:
                cols: 1
                spacing: '8dp'
                padding: ['20dp', '20dp', '20dp', '32dp']
                size_hint_y: None
                height: self.minimum_height

                SectionLabel:
                    text: 'CUSTOMER NAME'
                BWSInput:
                    id: customer_name
                    hint_text: 'e.g. Maria Santos'

                Widget:
                    size_hint_y: None
                    height: '4dp'

                SectionLabel:
                    text: 'GALLON TYPE'
                Spinner:
                    id: gallon_type
                    text: 'Round'
                    values: ['Round', 'Slim', 'Both']
                    size_hint_y: None
                    height: '48dp'
                    font_size: '15sp'
                    color: 0.102, 0.125, 0.173, 1
                    background_normal: ''
                    background_color: 1, 1, 1, 1

                Widget:
                    size_hint_y: None
                    height: '4dp'

                SectionLabel:
                    text: 'SERVICE TYPE'
                BoxLayout:
                    size_hint_y: None
                    height: '52dp'
                    padding: ['14dp', '0dp']
                    spacing: '12dp'
                    canvas.before:
                        Color:
                            rgba: 1, 1, 1, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [dp(8)]
                        Color:
                            rgba: 0.796, 0.835, 0.878, 1
                        Line:
                            rounded_rectangle: (self.x, self.y, self.width, self.height, dp(8))
                            width: 1
                    Label:
                        id: refill_label
                        text: 'Borrow Container'
                        color: 0.102, 0.125, 0.173, 1
                        font_size: '14sp'
                        halign: 'left'
                        text_size: self.width, None
                    Switch:
                        id: is_refill
                        size_hint_x: None
                        width: '80dp'
                        on_active: app.on_refill_toggle(self.active)

                Widget:
                    size_hint_y: None
                    height: '4dp'

                SectionLabel:
                    text: 'WATER PRICE (PHP)'
                BWSInput:
                    id: water_price
                    hint_text: '0.00'
                    input_filter: 'float'
                    keyboard_type: 'numeric'

                # Deposit section — hidden when refill is active
                BoxLayout:
                    id: deposit_section
                    orientation: 'vertical'
                    size_hint_y: None
                    height: '80dp'
                    spacing: '8dp'
                    SectionLabel:
                        text: 'CONTAINER DEPOSIT (PHP)'
                    BWSInput:
                        id: deposit_fee
                        hint_text: '0.00'
                        input_filter: 'float'
                        keyboard_type: 'numeric'

                Widget:
                    size_hint_y: None
                    height: '4dp'

                SectionLabel:
                    text: 'DELIVERY TIME (optional)'
                BWSInput:
                    id: delivery_time
                    hint_text: 'e.g. 09:30 AM'

                Widget:
                    size_hint_y: None
                    height: '16dp'

                BWSButton:
                    text: 'Save Order'
                    on_release: app.save_order()

# ── Screen: View Orders ───────────────────────────────────────────────────────

<ViewOrdersScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        # Header
        BoxLayout:
            size_hint_y: None
            height: '64dp'
            padding: ['16dp', '12dp']
            spacing: '12dp'
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: '<'
                size_hint_x: None
                width: '44dp'
                background_color: 0, 0, 0, 0
                color: 1, 1, 1, 1
                font_size: '22sp'
                bold: True
                on_release: app.go_back()
            Label:
                text: 'Orders by Date'
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                halign: 'left'
                text_size: self.width, None

        # Search bar
        BoxLayout:
            size_hint_y: None
            height: '68dp'
            padding: ['16dp', '8dp']
            spacing: '10dp'
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            BWSInput:
                id: filter_date
                hint_text: 'YYYY-MM-DD  (blank = today)'
                size_hint_x: 0.62
            BWSButton:
                text: 'Search'
                size_hint_x: 0.38
                height: '48dp'
                on_release: app.load_orders()

        ScrollView:
            GridLayout:
                id: orders_list
                cols: 1
                spacing: '10dp'
                padding: ['16dp', '14dp', '16dp', '14dp']
                size_hint_y: None
                height: self.minimum_height

# ── Screen: Metrics ───────────────────────────────────────────────────────────

<MetricsScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        BoxLayout:
            size_hint_y: None
            height: '64dp'
            padding: ['16dp', '12dp']
            spacing: '12dp'
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: '<'
                size_hint_x: None
                width: '44dp'
                background_color: 0, 0, 0, 0
                color: 1, 1, 1, 1
                font_size: '22sp'
                bold: True
                on_release: app.go_back()
            Label:
                text: 'Daily Metrics'
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                halign: 'left'
                text_size: self.width, None

        BoxLayout:
            size_hint_y: None
            height: '68dp'
            padding: ['16dp', '8dp']
            spacing: '10dp'
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            BWSInput:
                id: metrics_date
                hint_text: 'YYYY-MM-DD  (blank = today)'
                size_hint_x: 0.62
            BWSButton:
                text: 'Calculate'
                size_hint_x: 0.38
                height: '48dp'
                on_release: app.compute_metrics()

        ScrollView:
            GridLayout:
                id: metrics_content
                cols: 1
                spacing: '12dp'
                padding: ['16dp', '16dp', '16dp', '16dp']
                size_hint_y: None
                height: self.minimum_height

# ── Screen: Export ────────────────────────────────────────────────────────────

<ExportScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        BoxLayout:
            size_hint_y: None
            height: '64dp'
            padding: ['16dp', '12dp']
            spacing: '12dp'
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: '<'
                size_hint_x: None
                width: '44dp'
                background_color: 0, 0, 0, 0
                color: 1, 1, 1, 1
                font_size: '22sp'
                bold: True
                on_release: app.go_back()
            Label:
                text: 'Export Reports'
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                halign: 'left'
                text_size: self.width, None

        GridLayout:
            cols: 1
            spacing: '14dp'
            padding: ['24dp', '28dp', '24dp', '24dp']
            size_hint_y: None
            height: self.minimum_height

            SectionLabel:
                text: 'DATE TO EXPORT'
            BWSInput:
                id: export_date
                hint_text: 'YYYY-MM-DD  (blank = today)'

            Widget:
                size_hint_y: None
                height: '8dp'

            BWSButton:
                text: 'Export as CSV'
                on_release: app.export_csv()

            BWSOutlineButton:
                text: 'Export as PDF'
                on_release: app.export_pdf()

            Label:
                id: export_note
                text: ''
                color: 0.443, 0.502, 0.588, 1
                font_size: '12sp'
                size_hint_y: None
                height: '60dp'
                text_size: self.width, None
                halign: 'center'

        Widget:

# ── Screen: Customers ─────────────────────────────────────────────────────────

<CustomersScreen>:
    canvas.before:
        Color:
            rgba: 0.969, 0.980, 0.988, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'

        BoxLayout:
            size_hint_y: None
            height: '64dp'
            padding: ['16dp', '12dp']
            spacing: '12dp'
            canvas.before:
                Color:
                    rgba: 0.169, 0.424, 0.690, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Button:
                text: '<'
                size_hint_x: None
                width: '44dp'
                background_color: 0, 0, 0, 0
                color: 1, 1, 1, 1
                font_size: '22sp'
                bold: True
                on_release: app.go_back()
            Label:
                text: 'Customer List'
                color: 1, 1, 1, 1
                font_size: '18sp'
                bold: True
                halign: 'left'
                text_size: self.width, None

        ScrollView:
            GridLayout:
                id: customers_list
                cols: 1
                spacing: '8dp'
                padding: ['16dp', '14dp', '16dp', '14dp']
                size_hint_y: None
                height: self.minimum_height
"""


# ══════════════════════════════════════════════════════════════════════════════
#  SCREEN CLASSES (thin shells — logic lives in App)
# ══════════════════════════════════════════════════════════════════════════════

class HomeScreen(Screen):
    pass

class AddOrderScreen(Screen):
    pass

class ViewOrdersScreen(Screen):
    pass

class MetricsScreen(Screen):
    pass

class ExportScreen(Screen):
    pass

class CustomersScreen(Screen):
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  APP CLASS
# ══════════════════════════════════════════════════════════════════════════════

class BWSTrackerApp(App):

    def build(self):
        Builder.load_string(KV)

        # Database — stored in app's private data directory on mobile
        db_path = os.path.join(self.user_data_dir, 'water_tracker.db')
        self.db        = Database(db_path)
        self.cust_repo = CustomerRepository(self.db)
        self.order_repo = OrderRepository(self.db)
        seed_database(self.db, self.cust_repo, self.order_repo)

        # Screen manager
        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        for name, cls in [
            ('home',        HomeScreen),
            ('add_order',   AddOrderScreen),
            ('view_orders', ViewOrdersScreen),
            ('metrics',     MetricsScreen),
            ('export',      ExportScreen),
            ('customers',   CustomersScreen),
        ]:
            self.sm.add_widget(cls(name=name))

        # Populate home today bar after build
        Clock.schedule_once(self._refresh_home, 0.1)
        return self.sm

    # ── Navigation ────────────────────────────────────────────────────────────

    def go_to(self, name: str):
        if name == 'view_orders':
            self._load_orders_for_date(date.today().isoformat())
        elif name == 'metrics':
            self._compute_metrics_for_date(date.today().isoformat())
        elif name == 'customers':
            self._render_customers()
        self.sm.current = name

    def go_back(self):
        self._refresh_home()
        self.sm.current = 'home'

    # ── Home refresh ─────────────────────────────────────────────────────────

    def _refresh_home(self, *args):
        today   = date.today().isoformat()
        orders  = self.order_repo.find_by_date(today)
        m       = DailyMetrics.compute(orders, today)
        screen  = self.sm.get_screen('home')
        screen.ids.today_label.text = (
            f"Today  {today}     "
            f"{m.order_count} orders     "
            f"Cash In: \u20b1{m.combined_inflow:,.2f}"
        )

    # ── Add Order ─────────────────────────────────────────────────────────────

    def on_refill_toggle(self, active: bool):
        screen  = self.sm.get_screen('add_order')
        section = screen.ids.deposit_section
        section.height  = 0    if active else dp(80)
        section.opacity = 0    if active else 1
        screen.ids.deposit_fee.disabled = active
        screen.ids.refill_label.text = (
            'Refill  (client owns container)' if active else 'Borrow Container'
        )

    def save_order(self):
        screen = self.sm.get_screen('add_order')
        ids    = screen.ids

        name = ids.customer_name.text.strip()
        if not name:
            self._popup('Validation Error', 'Customer name cannot be blank.', ok=False)
            return

        gallon_type = ids.gallon_type.text
        is_refill   = ids.is_refill.active

        try:
            water_price = float(ids.water_price.text or '0')
            if water_price < 0:
                raise ValueError
        except ValueError:
            self._popup('Validation Error', 'Water price must be a valid positive number.', ok=False)
            return

        deposit_fee = 0.0
        if not is_refill:
            try:
                deposit_fee = float(ids.deposit_fee.text or '0')
                if deposit_fee < 0:
                    raise ValueError
            except ValueError:
                self._popup('Validation Error', 'Deposit fee must be a valid positive number.', ok=False)
                return

        delivery_time = ids.delivery_time.text.strip()

        try:
            customer, _ = self.cust_repo.get_or_create(name)
            order = Order.create(
                customer_id=customer.id, gallon_type=gallon_type,
                is_refill=is_refill, water_price=water_price,
                deposit_fee=deposit_fee, delivery_time=delivery_time,
            )
            order = self.order_repo.save(order)

            # Clear form
            for field_id in ('customer_name', 'water_price', 'deposit_fee', 'delivery_time'):
                ids[field_id].text = ''
            ids.is_refill.active = False
            ids.gallon_type.text = 'Round'
            self.on_refill_toggle(False)

            self._popup(
                'Order Saved',
                f'#{order.id}  {name}\n'
                f'{gallon_type}  \u2022  {"Refill" if is_refill else "Borrow"}\n'
                f'Total: \u20b1{order.total_amount:,.2f}',
                ok=True,
            )
        except ValueError as e:
            self._popup('Error', str(e), ok=False)

    # ── View Orders ───────────────────────────────────────────────────────────

    def load_orders(self):
        screen = self.sm.get_screen('view_orders')
        raw    = screen.ids.filter_date.text.strip()
        self._load_orders_for_date(self._resolve_date(raw))

    def _load_orders_for_date(self, target_date: str):
        screen = self.sm.get_screen('view_orders')
        orders = self.order_repo.find_by_date(target_date)
        grid   = screen.ids.orders_list
        grid.clear_widgets()

        # Count label
        count_lbl = Label(
            text=f'{len(orders)} order(s) for {target_date}',
            color=C_BLUE, font_size=sp(13), bold=True,
            size_hint_y=None, height=dp(32),
            halign='left', text_size=(dp(340), None),
        )
        grid.add_widget(count_lbl)

        if not orders:
            grid.add_widget(Label(
                text='No orders found for this date.',
                color=C_MUTED, font_size=sp(14),
                size_hint_y=None, height=dp(60),
                halign='center', text_size=(dp(300), None),
            ))
            return

        for o in orders:
            grid.add_widget(self._order_card(o))

        # Totals strip
        m = DailyMetrics.compute(orders, target_date)
        grid.add_widget(self._totals_strip(m))

    def _order_card(self, order: Order) -> Widget:
        card = BoxLayout(orientation='vertical', size_hint_y=None,
                         height=dp(120), padding=dp(14), spacing=dp(6))
        with card.canvas.before:
            Color(rgba=C_WHITE)
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
        card.bind(pos=lambda w, v, r=rect: setattr(r, 'pos', v),
                  size=lambda w, v, r=rect: setattr(r, 'size', v))

        # Row 1: name + type badge
        r1 = BoxLayout(size_hint_y=None, height=dp(26))
        r1.add_widget(Label(text=order.customer_name, color=C_TEXT,
                            font_size=sp(15), bold=True,
                            halign='left', text_size=(dp(200), None)))
        r1.add_widget(Label(
            text=f'{order.gallon_type}  \u2022  {order.service_label}',
            color=C_BLUE, font_size=sp(12),
            halign='right', text_size=(dp(120), None)))
        card.add_widget(r1)

        # Row 2: prices
        r2 = BoxLayout(size_hint_y=None, height=dp(22))
        r2.add_widget(Label(text=f'Water: \u20b1{order.water_price:,.2f}',
                            color=C_MUTED, font_size=sp(13),
                            halign='left', text_size=(dp(150), None)))
        r2.add_widget(Label(text=f'Deposit: \u20b1{order.deposit_fee:,.2f}',
                            color=C_MUTED, font_size=sp(13),
                            halign='right', text_size=(dp(150), None)))
        card.add_widget(r2)

        # Divider
        div = Widget(size_hint_y=None, height=dp(1))
        with div.canvas:
            Color(rgba=C_BORDER)
            div_rect = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, v, r=div_rect: setattr(r, 'pos', v),
                 size=lambda w, v, r=div_rect: setattr(r, 'size', v))
        card.add_widget(div)

        # Row 3: time + total
        r3 = BoxLayout(size_hint_y=None, height=dp(26))
        r3.add_widget(Label(text=f'Time: {order.delivery_time}',
                            color=C_MUTED, font_size=sp(12),
                            halign='left', text_size=(dp(170), None)))
        r3.add_widget(Label(
            text=f'TOTAL  \u20b1{order.total_amount:,.2f}',
            color=C_BLUE, font_size=sp(14), bold=True,
            halign='right', text_size=(dp(150), None)))
        card.add_widget(r3)
        return card

    def _totals_strip(self, m: DailyMetrics) -> Widget:
        strip = BoxLayout(size_hint_y=None, height=dp(68),
                          padding=[dp(16), dp(10)], spacing=dp(8))
        with strip.canvas.before:
            Color(rgba=C_YELLOW_BG)
            rect = RoundedRectangle(pos=strip.pos, size=strip.size, radius=[dp(10)])
        strip.bind(pos=lambda w, v, r=rect: setattr(r, 'pos', v),
                   size=lambda w, v, r=rect: setattr(r, 'size', v))

        def col(label, val):
            box = BoxLayout(orientation='vertical')
            box.add_widget(Label(text=label, color=C_MUTED, font_size=sp(10),
                                 halign='center', text_size=(dp(100), None),
                                 size_hint_y=None, height=dp(18)))
            box.add_widget(Label(text=f'\u20b1{val:,.2f}', color=C_TEXT,
                                 font_size=sp(14), bold=True,
                                 halign='center', text_size=(dp(100), None),
                                 size_hint_y=None, height=dp(24)))
            return box

        strip.add_widget(col('Water Sales', m.gross_water_sales))
        strip.add_widget(col('Deposits', m.total_deposits))
        strip.add_widget(col('Cash Inflow', m.combined_inflow))
        return strip

    # ── Metrics ───────────────────────────────────────────────────────────────

    def compute_metrics(self):
        screen = self.sm.get_screen('metrics')
        raw    = screen.ids.metrics_date.text.strip()
        self._compute_metrics_for_date(self._resolve_date(raw))

    def _compute_metrics_for_date(self, target_date: str):
        screen = self.sm.get_screen('metrics')
        orders = self.order_repo.find_by_date(target_date)
        m      = DailyMetrics.compute(orders, target_date)
        grid   = screen.ids.metrics_content
        grid.clear_widgets()

        grid.add_widget(Label(
            text=f'Analytics  \u2014  {target_date}',
            color=C_BLUE, font_size=sp(16), bold=True,
            size_hint_y=None, height=dp(40),
            halign='left', text_size=(dp(320), None),
        ))

        items = [
            ('Total Orders',        str(m.order_count),                   False),
            ('Gross Water Sales',   f'\u20b1{m.gross_water_sales:,.2f}',  True),
            ('Container Deposits',  f'\u20b1{m.total_deposits:,.2f}',     True),
            ('Combined Cash Inflow',f'\u20b1{m.combined_inflow:,.2f}',    True),
        ]
        for lbl, val, highlight in items:
            grid.add_widget(self._metric_card(lbl, val, highlight))

    def _metric_card(self, label: str, value: str, highlight: bool) -> Widget:
        card = BoxLayout(orientation='vertical', size_hint_y=None,
                         height=dp(80), padding=[dp(18), dp(12)], spacing=dp(4))
        bg = C_BLUE_LIGHT if highlight else C_WHITE
        with card.canvas.before:
            Color(rgba=bg)
            rect = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
        card.bind(pos=lambda w, v, r=rect: setattr(r, 'pos', v),
                  size=lambda w, v, r=rect: setattr(r, 'size', v))
        card.add_widget(Label(text=label, color=C_MUTED, font_size=sp(12),
                              halign='left', text_size=(dp(300), None),
                              size_hint_y=None, height=dp(20)))
        card.add_widget(Label(text=value,
                              color=C_BLUE if highlight else C_TEXT,
                              font_size=sp(24), bold=True,
                              halign='left', text_size=(dp(300), None),
                              size_hint_y=None, height=dp(36)))
        return card

    # ── Export ────────────────────────────────────────────────────────────────

    def export_csv(self):
        screen = self.sm.get_screen('export')
        raw    = screen.ids.export_date.text.strip()
        target = self._resolve_date(raw)
        orders = self.order_repo.find_by_date(target)
        if not orders:
            self._popup('No Data', f'No orders found for {target}.', ok=False)
            return
        try:
            path = os.path.join(self._export_dir(), f'sales_report_{target}.csv')
            CSVExporter.export(orders, target, path)
            screen.ids.export_note.text = f'Saved to:\n{path}'
            self._popup('CSV Exported', f'sales_report_{target}.csv\n\nSaved to your Downloads folder.', ok=True)
        except Exception as e:
            self._popup('Export Failed', str(e), ok=False)

    def export_pdf(self):
        if not REPORTLAB_AVAILABLE:
            self._popup('Unavailable', 'ReportLab is not installed on this device.', ok=False)
            return
        screen = self.sm.get_screen('export')
        raw    = screen.ids.export_date.text.strip()
        target = self._resolve_date(raw)
        orders = self.order_repo.find_by_date(target)
        if not orders:
            self._popup('No Data', f'No orders found for {target}.', ok=False)
            return
        try:
            path = os.path.join(self._export_dir(), f'sales_report_{target}.pdf')
            PDFExporter.export(orders, target, path)
            screen.ids.export_note.text = f'Saved to:\n{path}'
            self._popup('PDF Exported', f'sales_report_{target}.pdf\n\nSaved to your Downloads folder.', ok=True)
        except Exception as e:
            self._popup('Export Failed', str(e), ok=False)

    # ── Customers ─────────────────────────────────────────────────────────────

    def _render_customers(self):
        screen    = self.sm.get_screen('customers')
        grid      = screen.ids.customers_list
        grid.clear_widgets()
        customers = self.cust_repo.all()

        if not customers:
            grid.add_widget(Label(
                text='No customers yet.',
                color=C_MUTED, font_size=sp(14),
                size_hint_y=None, height=dp(60),
            ))
            return

        grid.add_widget(Label(
            text=f'{len(customers)} registered customer(s)',
            color=C_BLUE, font_size=sp(13), bold=True,
            size_hint_y=None, height=dp(30),
            halign='left', text_size=(dp(320), None),
        ))

        for c in customers:
            row = BoxLayout(size_hint_y=None, height=dp(56),
                            padding=[dp(16), dp(8)])
            with row.canvas.before:
                Color(rgba=C_WHITE)
                rect = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(8)])
            row.bind(pos=lambda w, v, r=rect: setattr(r, 'pos', v),
                     size=lambda w, v, r=rect: setattr(r, 'size', v))

            row.add_widget(Label(text=f'#{c.id}', color=C_MUTED,
                                 font_size=sp(12), size_hint_x=None, width=dp(36),
                                 halign='left', text_size=(dp(36), None)))
            row.add_widget(Label(text=c.name, color=C_TEXT, font_size=sp(15),
                                 bold=True, halign='left',
                                 text_size=(dp(280), None)))
            grid.add_widget(row)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _popup(self, title: str, message: str, ok: bool = True):
        btn_color = C_BLUE if ok else C_RED
        content   = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(16))
        content.add_widget(Label(
            text=message, color=C_TEXT, font_size=sp(14),
            size_hint_y=None, height=dp(90),
            halign='center', text_size=(dp(260), None),
        ))
        btn = Button(
            text='OK', size_hint_y=None, height=dp(44),
            background_color=btn_color, color=C_WHITE,
            background_normal='',
        )
        content.add_widget(btn)
        popup = Popup(
            title=title, content=content,
            size_hint=(0.88, None), height=dp(220),
            separator_color=C_BLUE,
        )
        btn.bind(on_release=popup.dismiss)
        popup.open()

    @staticmethod
    def _resolve_date(raw: str) -> str:
        try:
            datetime.strptime(raw, '%Y-%m-%d')
            return raw
        except ValueError:
            return date.today().isoformat()

    @staticmethod
    def _export_dir() -> str:
        # Android Downloads
        android_dl = '/storage/emulated/0/Download'
        if os.path.exists(android_dl):
            return android_dl
        # iOS / Desktop: current working directory
        return os.getcwd()


if __name__ == '__main__':
    BWSTrackerApp().run()
