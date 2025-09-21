import os
import sys
import subprocess
import shlex
import shutil
import psutil
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QLineEdit, 
                             QVBoxLayout, QWidget, QLabel, QHBoxLayout, QSplitter)
from PyQt5.QtCore import Qt, QTimer, QRegularExpression
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextCursor

class CommandHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Command format
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(0, 200, 0))  # Green
        self.highlighting_rules.append((QRegularExpression("^\\$ .*"), command_format))
        
        # Output format
        output_format = QTextCharFormat()
        output_format.setForeground(QColor(200, 200, 200))  # Light gray
        self.highlighting_rules.append((QRegularExpression("^[^\\$].*"), output_format))
        
        # Error format
        error_format = QTextCharFormat()
        error_format.setForeground(QColor(255, 0, 0))  # Red
        self.highlighting_rules.append((QRegularExpression("^Error:.*"), error_format))
        
        # Directory format
        dir_format = QTextCharFormat()
        dir_format.setForeground(QColor(100, 150, 255))  # Blue
        self.highlighting_rules.append((QRegularExpression(".*/$"), dir_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class TerminalWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_dir = os.getcwd()
        self.command_history = []
        self.history_index = -1
        self.setup_ui()
        self.print_welcome()
        
        # System monitoring timer
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_system_monitor)
        self.monitor_timer.start(2000)  # Update every 2 seconds

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # System monitor
        self.monitor_label = QLabel()
        self.monitor_label.setStyleSheet("background-color: #222; color: #0f0; padding: 5px;")
        self.monitor_label.setFont(QFont("Monospace", 9))
        layout.addWidget(self.monitor_label)
        
        # Terminal output
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("Monospace", 10))
        self.output_area.setStyleSheet("background-color: #000; color: #ccc;")
        self.highlighter = CommandHighlighter(self.output_area.document())
        layout.addWidget(self.output_area)
        
        # Input area
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(5, 5, 5, 5)
        
        self.prompt_label = QLabel(f"{os.getlogin()}@pyterm:$ ")
        self.prompt_label.setFont(QFont("Monospace", 10))
        self.prompt_label.setStyleSheet("color: #0f0;")
        self.prompt_label.setMinimumWidth(150)
        
        self.input_field = QLineEdit()
        self.input_field.setFont(QFont("Monospace", 10))
        self.input_field.setStyleSheet("background-color: #111; color: #fff; border: none;")
        self.input_field.returnPressed.connect(self.execute_command)
        
        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.input_field)
        
        layout.addLayout(input_layout)
        self.setLayout(layout)
        
        # Set focus to input field
        self.input_field.setFocus()

    def print_welcome(self):
        welcome_msg = f"""
Python Terminal Emulator
Type 'help' for available commands
Current directory: {self.current_dir}
"""
        self.output_area.append(welcome_msg)

    def update_prompt(self):
        # Show only the current directory name, not the full path
        dir_name = os.path.basename(self.current_dir)
        if not dir_name:
            dir_name = "/"
        self.prompt_label.setText(f"{os.getlogin()}@pyterm:{dir_name}$ ")

    def execute_command(self):
        command = self.input_field.text().strip()
        self.input_field.clear()
        
        if not command:
            return
            
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # Display command
        self.output_area.append(f"$ {command}")
        
        # Handle command
        if command.lower() == "exit":
            QApplication.quit()
        elif command.lower() == "help":
            self.show_help()
        elif command.startswith("cd "):
            self.change_directory(command[3:])
        elif command == "cd":
            self.change_directory("")
        elif command == "pwd":
            self.output_area.append(self.current_dir)
        elif command == "ls" or command.startswith("ls "):
            self.list_files(command)
        elif command.startswith("mkdir "):
            self.make_directory(command[6:])
        elif command.startswith("rm "):
            self.remove_file_or_dir(command[3:])
        elif command.startswith("cp "):
            self.copy_file_or_dir(command)
        elif command.startswith("mv "):
            self.move_file_or_dir(command)
        elif command == "clear":
            self.output_area.clear()
        elif command == "history":
            self.show_history()
        elif command == "ps":
            self.show_processes()
        elif command == "top":
            self.show_system_stats()
        else:
            self.execute_system_command(command)
            
        # Scroll to bottom
        self.output_area.moveCursor(QTextCursor.End)

    def change_directory(self, path):
        try:
            if not path:
                path = os.path.expanduser("~")
            new_dir = os.path.abspath(os.path.join(self.current_dir, path))
            if os.path.isdir(new_dir):
                self.current_dir = new_dir
                self.update_prompt()
            else:
                self.output_area.append(f"Error: Directory not found: {path}")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def list_files(self, command):
        try:
            parts = shlex.split(command)
            path = self.current_dir
            show_all = False
            long_format = False
            
            if len(parts) > 1:
                # Handle flags and path
                if parts[1].startswith('-'):
                    flags = parts[1]
                    show_all = 'a' in flags
                    long_format = 'l' in flags
                    if len(parts) > 2:
                        path = os.path.join(self.current_dir, parts[2])
                else:
                    path = os.path.join(self.current_dir, parts[1])
            
            if not os.path.exists(path):
                self.output_area.append(f"Error: Path not found: {path}")
                return
                
            if os.path.isfile(path):
                # List details of a single file
                stat = os.stat(path)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                self.output_area.append(f"{'-' if os.path.isfile(path) else 'd'}{'r' if os.access(path, os.R_OK) else '-'}{'w' if os.access(path, os.W_OK) else '-'}{'x' if os.access(path, os.X_OK) else '-'} {size:8} {mtime} {os.path.basename(path)}")
            else:
                # List directory contents
                files = os.listdir(path)
                if not show_all:
                    files = [f for f in files if not f.startswith('.')]
                    
                if long_format:
                    for f in files:
                        full_path = os.path.join(path, f)
                        stat = os.stat(full_path)
                        size = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                        self.output_area.append(f"{'-' if os.path.isfile(full_path) else 'd'}{'r' if os.access(full_path, os.R_OK) else '-'}{'w' if os.access(full_path, os.W_OK) else '-'}{'x' if os.access(full_path, os.X_OK) else '-'} {size:8} {mtime} {f}")
                else:
                    # Group directories first
                    dirs = [f for f in files if os.path.isdir(os.path.join(path, f))]
                    files = [f for f in files if os.path.isfile(os.path.join(path, f))]
                    
                    # Format in columns
                    max_len = max([len(f) for f in files + dirs] + [0]) + 2
                    per_line = max(1, 80 // max_len)
                    
                    line = ""
                    for i, d in enumerate(dirs):
                        line += f"{d}/".ljust(max_len)
                        if (i + 1) % per_line == 0:
                            self.output_area.append(line)
                            line = ""
                    
                    for i, f in enumerate(files):
                        line += f"{f}".ljust(max_len)
                        if (i + 1) % per_line == 0:
                            self.output_area.append(line)
                            line = ""
                    
                    if line:
                        self.output_area.append(line)
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def make_directory(self, path):
        try:
            if not path:
                self.output_area.append("Error: mkdir requires a directory name")
                return
                
            full_path = os.path.join(self.current_dir, path)
            os.makedirs(full_path, exist_ok=True)
            self.output_area.append(f"Created directory: {path}")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def remove_file_or_dir(self, path):
        try:
            if not path:
                self.output_area.append("Error: rm requires a path")
                return
                
            full_path = os.path.join(self.current_dir, path)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
                self.output_area.append(f"Removed directory: {path}")
            else:
                os.remove(full_path)
                self.output_area.append(f"Removed file: {path}")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def copy_file_or_dir(self, command):
        try:
            parts = shlex.split(command)
            if len(parts) < 3:
                self.output_area.append("Error: cp requires source and destination")
                return
                
            src = os.path.join(self.current_dir, parts[1])
            dst = os.path.join(self.current_dir, parts[2])
            
            if os.path.isdir(src):
                shutil.copytree(src, dst)
                self.output_area.append(f"Copied directory: {parts[1]} to {parts[2]}")
            else:
                shutil.copy2(src, dst)
                self.output_area.append(f"Copied file: {parts[1]} to {parts[2]}")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def move_file_or_dir(self, command):
        try:
            parts = shlex.split(command)
            if len(parts) < 3:
                self.output_area.append("Error: mv requires source and destination")
                return
                
            src = os.path.join(self.current_dir, parts[1])
            dst = os.path.join(self.current_dir, parts[2])
            
            shutil.move(src, dst)
            self.output_area.append(f"Moved: {parts[1]} to {parts[2]}")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def execute_system_command(self, command):
        try:
            # Change to current directory before executing
            env = os.environ.copy()
            process = subprocess.Popen(
                command, 
                shell=True, 
                cwd=self.current_dir,
                env=env,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if stdout:
                self.output_area.append(stdout)
            if stderr:
                self.output_area.append(f"Error: {stderr}")
        except Exception as e:
            self.output_area.append(f"Error executing command: {str(e)}")

    def show_help(self):
        help_text = """
Available commands:
  cd [dir]         Change directory
  pwd              Show current directory
  ls [options]     List files (-a: show hidden, -l: long format)
  mkdir <dir>      Create directory
  rm <path>        Remove file or directory
  cp <src> <dst>   Copy file or directory
  mv <src> <dst>   Move file or directory
  clear            Clear screen
  history          Show command history
  ps               Show running processes
  top              Show system statistics
  exit             Exit terminal
"""
        self.output_area.append(help_text)

    def show_history(self):
        for i, cmd in enumerate(self.command_history):
            self.output_area.append(f"{i+1}: {cmd}")

    def show_processes(self):
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
                processes.append(proc.info)
                
            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            
            self.output_area.append("PID\tNAME\tUSER\tCPU%\tMEMORY")
            for p in processes[:10]:  # Show top 10
                mem_mb = p['memory_info'].rss / 1024 / 1024 if p['memory_info'] else 0
                self.output_area.append(f"{p['pid']}\t{p['name']}\t{p['username']}\t{p['cpu_percent']:.1f}\t{mem_mb:.1f}MB")
        except Exception as e:
            self.output_area.append(f"Error: {str(e)}")

    def update_system_monitor(self):
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            monitor_text = f"CPU: {cpu_percent}% | Memory: {memory.percent}% | Disk: {disk.percent}%"
            self.monitor_label.setText(monitor_text)
        except:
            self.monitor_label.setText("System monitor unavailable")

    def show_system_stats(self):
        try:
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(percpu=True)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            self.output_area.append("=== SYSTEM STATISTICS ===")
            self.output_area.append(f"CPU Cores: {cpu_count}")
            self.output_area.append("CPU Usage per core:")
            for i, usage in enumerate(cpu_percent):
                self.output_area.append(f"  Core {i+1}: {usage}%")
            
            self.output_area.append(f"Memory Total: {memory.total / 1024 / 1024 / 1024:.1f} GB")
            self.output_area.append(f"Memory Used: {memory.used / 1024 / 1024 / 1024:.1f} GB ({memory.percent}%)")
            self.output_area.append(f"Disk Total: {disk.total / 1024 / 1024 / 1024:.1f} GB")
            self.output_area.append(f"Disk Used: {disk.used / 1024 / 1024 / 1024:.1f} GB ({disk.percent}%)")
        except Exception as e:
            self.output_area.append(f"Error getting system stats: {str(e)}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.command_history and self.history_index > 0:
                self.history_index -= 1
                self.input_field.setText(self.command_history[self.history_index])
        elif event.key() == Qt.Key_Down:
            if self.command_history and self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.input_field.setText(self.command_history[self.history_index])
            else:
                self.history_index = len(self.command_history)
                self.input_field.clear()
        else:
            super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Terminal")
        self.setGeometry(100, 100, 800, 600)
        
        self.terminal = TerminalWidget()
        self.setCentralWidget(self.terminal)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
