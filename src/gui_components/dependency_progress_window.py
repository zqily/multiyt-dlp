"""
Defines a reusable Toplevel window for showing dependency download progress.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Any


class DependencyProgressWindow(tk.Toplevel):
    """A Toplevel window for displaying dependency download progress."""

    def __init__(self, master: tk.Tk, cancel_callback: Callable[[], None]):
        """
        Initializes the dependency progress window.

        Args:
            master: The parent window.
            cancel_callback: The function to call when the cancel button is pressed.
        """
        super().__init__(master)
        self.is_visible = False
        self._cancel_callback = cancel_callback
        self.withdraw()  # Start hidden

    def show(self, title: str):
        """
        Makes the window visible and configures it.

        Args:
            title: The title to display for the window.
        """
        if self.is_visible:
            return

        self.is_visible = True
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.transient(self.master)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._create_widgets()
        self.deiconify() # Show the window
        self.grab_set()

    def _create_widgets(self):
        """Creates the widgets for the progress window."""
        self.dep_progress_label = ttk.Label(self, text="Initializing...")
        self.dep_progress_label.pack(fill=tk.X, padx=10, pady=10)
        self.dep_progress_bar = ttk.Progressbar(self, orient='horizontal', length=380)
        self.dep_progress_bar.pack(pady=10)

        cancel_button = ttk.Button(self, text="Cancel", command=self._on_cancel)
        cancel_button.pack(pady=5)

    def _on_cancel(self):
        """Handles the cancel action."""
        if messagebox.askyesno("Confirm Cancel", "Are you sure you want to cancel the download?", parent=self):
            self._cancel_callback()

    def update_progress(self, data: Dict[str, Any]):
        """
        Updates the progress bar and label text.

        Args:
            data: A dictionary containing progress information.
                  Expected keys: 'text' (str), 'status' (str: 'determinate' or 'indeterminate'),
                  'value' (float).
        """
        if not self.is_visible:
            return

        self.dep_progress_label.config(text=data.get('text', ''))
        if data.get('status') == 'indeterminate':
            self.dep_progress_bar.config(mode='indeterminate')
            self.dep_progress_bar.start(10)
        else:
            self.dep_progress_bar.stop()
            self.dep_progress_bar.config(mode='determinate')
            self.dep_progress_bar['value'] = data.get('value', 0)

    def close(self):
        """Closes and destroys the window."""
        if self.winfo_exists():
            self.dep_progress_bar.stop()
            self.grab_release()
            self.destroy()
        self.is_visible = False