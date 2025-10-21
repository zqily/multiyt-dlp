"""
Defines a context menu for the job list Treeview.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class JobContextMenu(tk.Menu):
    """Context menu for the downloads Treeview."""

    def __init__(self, master: tk.Tk, tree: ttk.Treeview, retry_callback: Callable[[], None], open_folder_callback: Callable[[], None]):
        """
        Initializes the context menu.

        Args:
            master: The parent widget.
            tree: The Treeview widget this menu is associated with.
            retry_callback: Function to call for the "Retry" action.
            open_folder_callback: Function to call for the "Open Folder" action.
        """
        super().__init__(master, tearoff=0)
        self.tree = tree
        self.add_command(label="Open Output Folder", command=open_folder_callback)
        self.add_command(label="Retry Failed Download(s)", command=retry_callback)

    def show(self, event):
        """
        Displays the context menu at the cursor's position.

        It also enables/disables menu items based on the current selection.

        Args:
            event: The event object (e.g., from a mouse click).
        """
        selection = self.tree.selection()
        if not selection:
            item_id = self.tree.identify_row(event.y)
            if not item_id:
                return
            self.tree.selection_set(item_id)
            selection = (item_id,)

        is_failed = any('failed' in self.tree.item(item_id, 'tags') for item_id in selection)
        self.entryconfig("Retry Failed Download(s)", state='normal' if is_failed else 'disabled')

        self.post(event.x_root, event.y_root)