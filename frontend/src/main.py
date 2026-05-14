import sys
import os
import random
import json
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Label, ProgressBar, Sparkline, DataTable
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from textual import on
from rich.text import Text

def setup_test_environment(data_path: str, rules_path: str):
    """Generates test rules and a test binary with injected signatures."""
    # 1. Create Rules
    if not os.path.exists(rules_path):
        print(f"Generating default rules at {rules_path}...")
        rules = [
            {"name": "ZIP Archive (PKZIP)", "hex": "50 4B 03 04"},
            {"name": "PDF Document", "hex": "25 50 44 46 2D"}
        ]
        with open(rules_path, "w") as f:
            json.dump(rules, f, indent=4)

    # 2. Create Binary
    if not os.path.exists(data_path):
        print(f"Generating test file at {data_path}...")
        with open(data_path, "wb") as f:
            # 512KB of pure zeros
            f.write(b'\x00' * (512 * 1024))
            
            # 512KB of random bytes
            random_bytes = bytearray(random.getrandbits(8) for _ in range(512 * 1024))
            
            # Inject a fake ZIP header at offset 512KB + 256 bytes (0x00080100)
            zip_header = b'\x50\x4B\x03\x04'
            random_bytes[256:260] = zip_header
            
            f.write(random_bytes)

class ChunkStatsMessage(Message):
    def __init__(self, entropy: float, histogram: list[int], matches: list[tuple[str, int]]) -> None:
        self.entropy = entropy
        self.histogram = histogram
        self.matches = matches
        super().__init__()

class HexViewer(Static):
    offset = reactive(0)

    def __init__(self, engine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = engine
        self.file_size = engine.get_file_size()
        self.lines_per_page = 10
        self.bytes_per_line = 16

    def on_resize(self, event) -> None:
        self.lines_per_page = max(1, event.size.height - 2)
        self.refresh_hex()

    def watch_offset(self, old_offset: int, new_offset: int) -> None:
        self.refresh_hex()

    def refresh_hex(self) -> None:
        chunk_size = self.lines_per_page * self.bytes_per_line
        try:
            stats = self.engine.get_chunk_stats(self.offset, chunk_size)
        except ValueError:
            return 

        data = stats.data
        rich_text = Text()

        for i in range(0, len(data), self.bytes_per_line):
            chunk = data[i:i+self.bytes_per_line]
            current_offset = self.offset + i
            
            rich_text.append(f"{current_offset:08X}  ", style="bold cyan")
            
            hex_length = 0
            for b in chunk:
                if b == 0:
                    rich_text.append("00 ", style="dim")
                else:
                    # Highlight bytes that are part of the injected ZIP header for visibility
                    if chunk == b'\x50\x4B\x03\x04' and b in [0x50, 0x4B, 0x03, 0x04]:
                        rich_text.append(f"{b:02X} ", style="bold red")
                    else:
                        rich_text.append(f"{b:02X} ", style="green")
                hex_length += 3
            
            padding = (self.bytes_per_line * 3) - hex_length
            rich_text.append(" " * padding + " |")
            
            for b in chunk:
                if 32 <= b <= 126:
                    rich_text.append(chr(b), style="white")
                else:
                    rich_text.append(".", style="dim")
            rich_text.append("|\n")

        self.update(rich_text)
        self.post_message(ChunkStatsMessage(stats.entropy, stats.histogram, stats.matches))

class DigitalArchaeologyApp(App):
    TITLE = "Digital Archaeology & Entropy Forensics"
    
    CSS = """
    #main-container { height: 1fr; layout: horizontal; }
    HexViewer { width: 2fr; height: 1fr; padding: 1 2; background: $surface; }
    #analytics { width: 1fr; height: 1fr; border-left: solid $primary; padding: 1 2; background: $surface-darken-1; }
    .panel-title { text-style: bold; color: $accent; margin-top: 1; margin-bottom: 1; }
    #entropy-label { margin-bottom: 2; color: $text-muted; }
    #histogram-sparkline { height: 5; margin-bottom: 2; }
    #matches-table { height: 1fr; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("down,j", "scroll_down", "Down", show=True),
        Binding("up,k", "scroll_up", "Up", show=True),
        Binding("pagedown", "page_down", "Page Down", show=True),
        Binding("pageup", "page_up", "Page Up", show=True),
    ]

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield HexViewer(self.engine, id="hex-viewer")
            with Vertical(id="analytics"):
                yield Label("Shannon Entropy (bits/byte)", classes="panel-title")
                yield ProgressBar(total=8.0, id="entropy-bar")
                yield Label("0.0000 / 8.0000", id="entropy-label")
                
                yield Label("Byte Frequency", classes="panel-title")
                yield Sparkline(id="histogram-sparkline")

                yield Label("Detected Signatures", classes="panel-title")
                yield DataTable(id="matches-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.add_columns("Offset", "Signature")

    @on(ChunkStatsMessage)
    def update_analytics(self, event: ChunkStatsMessage) -> None:
        self.query_one("#entropy-bar", ProgressBar).progress = event.entropy
        self.query_one("#entropy-label", Label).update(f"{event.entropy:.4f} / 8.0000")
        
        downsampled = [sum(event.histogram[i*4:(i+1)*4]) for i in range(64)]
        self.query_one("#histogram-sparkline", Sparkline).data = downsampled

        table = self.query_one("#matches-table", DataTable)
        table.clear()
        for match_name, match_offset in event.matches:
            table.add_row(f"{match_offset:08X}", match_name)

    def action_scroll_down(self) -> None:
        viewer = self.query_one("#hex-viewer", HexViewer)
        viewer.offset = min(viewer.offset + viewer.bytes_per_line, max(0, viewer.file_size - viewer.bytes_per_line))

    def action_scroll_up(self) -> None:
        viewer = self.query_one("#hex-viewer", HexViewer)
        viewer.offset = max(viewer.offset - viewer.bytes_per_line, 0)

    def action_page_down(self) -> None:
        viewer = self.query_one("#hex-viewer", HexViewer)
        step = viewer.lines_per_page * viewer.bytes_per_line
        viewer.offset = min(viewer.offset + step, max(0, viewer.file_size - viewer.bytes_per_line))
        viewer.offset -= viewer.offset % viewer.bytes_per_line

    def action_page_up(self) -> None:
        viewer = self.query_one("#hex-viewer", HexViewer)
        step = viewer.lines_per_page * viewer.bytes_per_line
        viewer.offset = max(viewer.offset - step, 0)
        viewer.offset -= viewer.offset % viewer.bytes_per_line

def main():
    try:
        import archaeology_engine
    except ImportError as e:
        print(f"Failed to load Rust engine: {e}")
        sys.exit(1)

    data_path = "/app/data/test_sample.bin"
    rules_path = "/app/rules/default_rules.json"
    
    setup_test_environment(data_path, rules_path)

    engine = archaeology_engine.Engine(data_path)
    # Load the rules into the engine
    try:
        engine.load_rules(rules_path)
    except Exception as e:
        print(f"Failed to load rules: {e}")
        sys.exit(1)

    app = DigitalArchaeologyApp(engine)
    app.run()

if __name__ == "__main__":
    main()