import html.parser
import json
import os
import stat
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
import zipfile
from urllib.parse import urlparse
from packaging import version
from datetime import datetime, timezone
import logging
import uuid
import appdirs
import requests
import tkinter as tk
from dotenv import load_dotenv
from PIL import Image, ImageTk
from tkinter import ttk, filedialog, messagebox, simpledialog
load_dotenv()

def get_resource_path(filename):
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

class LoggerWriter:

    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            self.level(message)

    def flush(self):
        pass

class MLStripper(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

def get_version():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    version_file = os.path.join(app_dir, 'version.json')
    try:
        with open(version_file, 'r') as f:
            version_data = json.load(f)
            return version_data.get('version', 'Unknown')
    except Exception as e:
        logging.info(f'Error reading version file: {e}')
        return 'Unknown'

class BuoyUI:

    def __init__(self, root):
        self.root = root
        self.app_data_dir = appdirs.user_data_dir('Hook_Line_Sinker_Reborn', 'PawsHLSR')
        self.setup_logging()
        self.gui_queue = queue.Queue()
        self.gdweave_queue = queue.Queue()
        self.load_settings()
        self.dark_mode_colors = {
            'bg': '#2b2b2b', 'fg': '#ffffff', 'select_bg': '#404040', 
            'select_fg': '#ffffff', 'button_bg': '#404040', 'button_fg': '#ffffff', 
            'entry_bg': '#333333', 'entry_fg': '#ffffff', 'frame_bg': '#1e1e1e', 
            'frame_fg': '#ffffff', 'menu_bg': '#2b2b2b', 'menu_fg': '#ffffff', 
            'tab_bg': '#333333', 'tab_fg': '#ffffff', 'tab_selected_bg': '#404040', 
            'tab_selected_fg': '#ffffff', 'scrollbar_bg': '#404040', 
            'scrollbar_fg': '#666666', 'highlight_bg': '#3d6a99', 
            'highlight_fg': '#ffffff', 'error_bg': '#992e2e', 'error_fg': '#ffffff', 
            'success_bg': '#2e9959', 'success_fg': '#ffffff'
        }
        self.dark_mode = tk.BooleanVar(value=self.settings.get('dark_mode', True))
        version = get_version()
        self.root.title(f'Buoy v{version}')
        if not self.settings.get('windowed_mode', True):
            self.root.state('zoomed')
        else:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 800
            window_height = 640
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
        self.root.minsize(800, 640)
        icon_path = get_resource_path('images/icon.ico')
        if os.path.exists(icon_path):
            if platform.system() == 'Windows':
                self.root.iconbitmap(icon_path)
            elif platform.system() == 'Linux':
                img = tk.PhotoImage(file=icon_path)
                self.root.tk.call('wm', 'iconphoto', self.root._w, img)
        else:
            logging.info('Warning: icon.ico not found')
        self.app_data_dir = appdirs.user_data_dir('Hook_Line_Sinker_Reborn', 'PawsHLSR')
        self.mods_dir = os.path.join(self.app_data_dir, 'mods')
        self.mod_cache_file = os.path.join(self.app_data_dir, 'mod_cache.json')
        os.makedirs(self.mods_dir, exist_ok=True)
        self.available_mods = []
        self.installed_mods = []
        TOOLS = 'Tools'
        COSMETICS = 'Cosmetics'
        LIBRARIES = 'Libraries'
        MODS = 'Mods'
        MISC = 'Misc'
        self.filtered_installed_mods = []
        self.mod_categories = {}
        self.available_sort_by = tk.StringVar(value=self.settings.get('available_sort_by', 'Last Updated'))
        self.installed_sort_by = tk.StringVar(value=self.settings.get('installed_sort_by', 'Recently Installed'))
        self.last_available_category = self.settings.get('available_category', 'All')
        self.last_installed_category = self.settings.get('installed_category', 'All')
        self.load_mod_cache()
        self.mod_downloading = False
        self.windowed_mode = tk.BooleanVar(value=self.settings.get('windowed_mode', True))
        self.auto_update = tk.BooleanVar(value=self.settings.get('auto_update', True))
        self.notifications = tk.BooleanVar(value=self.settings.get('notifications', False))
        self.theme = tk.StringVar(value=self.settings.get('theme', 'System'))
        self.show_nsfw = tk.BooleanVar(value=self.settings.get('show_nsfw', False))
        self.show_deprecated = tk.BooleanVar(value=self.settings.get('show_deprecated', False))
        self.game_path_entry = tk.StringVar(value=self.settings.get('game_path', ''))
        logging.info(f'Initial game path: {self.game_path_entry.get()}')
        self.create_status_bar()
        self.notebook = None
        self.mod_limit_disabled = False
        self.create_rotating_backup()
        logging.info('Made rotating backup')
        self.create_main_ui()
        if self.dark_mode.get():
            self.toggle_dark_mode(show_restart_prompt=False)
        self.mod_limit_disabled = False
        self.show_discord_prompt()
        self.check_for_duplicate_mods()
        self.multi_mod_warning_shown = False

    def create_server_browser_tab(self):
        """Creates the Server Browser tab and populates it with content."""
        server_browser_frame = ttk.Frame(self.notebook)
        self.notebook.add(server_browser_frame, text="Server Browser")  # Add tab

        # Define the server list table
        self.server_list = ttk.Treeview(server_browser_frame)
        self.server_list['columns'] = ('lobby_name', 'current_players', 'max_players', 'lobby_code', '18plus')
        self.server_list.column("#0", width=0, stretch=tk.NO)
        self.server_list.column("lobby_name", anchor=tk.W, width=200)
        self.server_list.column("18plus", anchor=tk.W, width=30)
        self.server_list.column("current_players", anchor=tk.W, width=100)
        self.server_list.column("max_players", anchor=tk.W, width=100)
        self.server_list.column("lobby_code", anchor=tk.W, width=100)

        self.server_list.heading("#0", text="", anchor=tk.W)
        self.server_list.heading("lobby_name", text="Lobby Name", anchor=tk.W)
        self.server_list.heading("18plus", text="18+", anchor=tk.W)
        self.server_list.heading("current_players", text="Current Players", anchor=tk.W)
        self.server_list.heading("max_players", text="Max Players", anchor=tk.W)
        self.server_list.heading("lobby_code", text="Lobby Code", anchor=tk.W)

        self.server_list.pack(fill=tk.BOTH, expand=True)

        # Initial update
        self.update_server_list()

    def update_server_list(self):
        try:
            # Fetch server data from the endpoint
            response = requests.get('http://127.0.0.1:5000/servers', timeout=5)
            response.raise_for_status()  # Raise an error for HTTP issues

            # Get the list of servers from the response
            self.server_data = response.json().get('servers', [])
            print(self.server_data)

            # Clear the existing entries in the server list
            self.server_list.delete(*self.server_list.get_children())

            # Add new server data to the list
            for server in self.server_data:
                self.server_list.insert('', 'end', values=(
                    server.get('lobby_name', 'Unknown'),
                    server.get('current_players', 0),
                    server.get('max_players', 0),
                    server.get('lobby_code', 'N/A'),
                    "Yes" if server.get('18plus', False) else "No"  # Display 'Yes' or 'No' for 18plus
                ))
        except requests.exceptions.RequestException as e:
            print(f"Error updating server list: {e}")
        finally:
            # Schedule the next update
            self.root.after(15000, self.update_server_list)  # Update every 15 seconds

    def save_sort_preferences(self):
        self.settings.update({'available_sort_by': self.available_sort_by.get(), 'installed_sort_by': self.installed_sort_by.get()})
        self.save_settings()

    def toggle_mod_limit(self):
        self.mod_limit_disabled = not self.mod_limit_disabled
        if self.mod_limit_disabled:
            messagebox.showinfo('Easter Egg', 'Mod selection limit warnings disabled. Please be careful when installing mods.')
        else:
            messagebox.showinfo('Easter Egg', 'Mod selection limit warnings re-enabled.')

    def toggle_dark_mode(self, show_restart_prompt=True):
        is_dark = True
        style = ttk.Style()

        style.theme_use('default')
        style.configure('TRadiobutton', background=self.dark_mode_colors['bg'], foreground=self.dark_mode_colors['fg'])
        style.map('TRadiobutton', foreground=[('active', 'black')], background=[('active', self.dark_mode_colors['highlight_bg'])])
        style.configure('TFrame', background=self.dark_mode_colors['bg'])
        style.configure('TLabel', background=self.dark_mode_colors['bg'], foreground=self.dark_mode_colors['fg'])
        style.configure('TButton', background=self.dark_mode_colors['button_bg'], foreground=self.dark_mode_colors['button_fg'])
        style.map('TButton', background=[('disabled', '#555555'), ('active', self.dark_mode_colors['highlight_bg'])], foreground=[('disabled', '#999999')])
        style.configure('TEntry', fieldbackground=self.dark_mode_colors['entry_bg'], foreground=self.dark_mode_colors['entry_fg'])
        style.configure('TLabelframe', background=self.dark_mode_colors['bg'])
        style.configure('TLabelframe.Label', background=self.dark_mode_colors['bg'], foreground=self.dark_mode_colors['fg'])
        style.configure('TNotebook', background=self.dark_mode_colors['bg'])
        style.configure('TNotebook.Tab', background=self.dark_mode_colors['tab_bg'], foreground=self.dark_mode_colors['tab_fg'], padding=[10, 2])
        style.map('TNotebook.Tab', background=[('selected', self.dark_mode_colors['tab_selected_bg'])], foreground=[('selected', self.dark_mode_colors['tab_selected_fg'])], expand=[('selected', [1, 1, 1, 0])])
        style.configure('Treeview', background=self.dark_mode_colors['bg'], foreground=self.dark_mode_colors['fg'], fieldbackground=self.dark_mode_colors['bg'])
        style.configure('Treeview.Heading', background=self.dark_mode_colors['button_bg'], foreground=self.dark_mode_colors['button_fg'])
        style.map('Treeview', background=[('selected', self.dark_mode_colors['select_bg'])], foreground=[('selected', self.dark_mode_colors['select_fg'])])
        style.map('TCheckbutton', background=[('active', 'darkgrey')])
        style.configure('TCheckbutton', indicatorbackground=self.dark_mode_colors['bg'], indicatorforeground='white', background=self.dark_mode_colors['bg'], foreground='white')
        listboxes = [self.available_listbox, self.installed_listbox, self.mod_details, self.modpacks_listbox, self.modpack_details]
        listboxes = [lb for lb in listboxes if lb is not None]
        for listbox in listboxes:
            listbox.configure(bg=self.dark_mode_colors['bg'], fg=self.dark_mode_colors['fg'], selectbackground=self.dark_mode_colors['select_bg'], selectforeground=self.dark_mode_colors['select_fg'])
        self.root.configure(bg=self.dark_mode_colors['bg'])

    def setup_logging(self):
        log_dir = os.path.dirname(os.path.join(self.app_data_dir, 'latestlog.txt'))
        os.makedirs(log_dir, exist_ok=True)
        error_log = os.path.join(self.app_data_dir, 'latestlog.txt')
        with open(error_log, 'w') as f:
            f.write('=' * 80 + '\n')
            f.write('Buoy Error Log\n')
            f.write('This log only contains errors and important messages\n')
            f.write('=' * 80 + '\n\n')
        error_handler = logging.FileHandler(error_log, mode='a')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
        full_log = os.path.join(self.app_data_dir, 'fulllatestlog.txt')
        with open(full_log, 'w') as f:
            f.write('=' * 80 + '\n')
            f.write('Buoy Full Debug Log\n')
            f.write('This log contains all debug messages and program activity\n')
            f.write('=' * 80 + '\n\n')
        full_handler = logging.FileHandler(full_log, mode='a')
        full_handler.setLevel(logging.DEBUG)
        full_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S'))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(full_handler)
        sys.stdout = LoggerWriter(logging.info)
        sys.stderr = LoggerWriter(logging.error)

    def open_latest_log(self):
        log_path = os.path.join(self.app_data_dir, 'latestlog.txt')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            log_window = tk.Toplevel(self.root)
            log_window.title('Buoy Log')
            log_window.geometry('800x600')
            log_window.configure(background=self.dark_mode_colors['bg'])
            icon_path = get_resource_path('images/icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)
            main_frame = ttk.Frame(log_window)
            main_frame.pack(expand=True, fill='both', padx=5, pady=5)
            main_frame.grid_columnconfigure(0, weight=1)
            main_frame.grid_rowconfigure(0, weight=1)
            text_frame = ttk.Frame(main_frame)
            text_frame.grid(row=0, column=0, sticky='nsew')
            text_frame.grid_columnconfigure(0, weight=1)
            text_frame.grid_rowconfigure(0, weight=1)
            log_text = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10), bg=self.dark_mode_colors['bg'], fg=self.dark_mode_colors['fg'])
            log_text.grid(row=0, column=0, sticky='nsew')
            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=log_text.yview)
            scrollbar.grid(row=0, column=1, sticky='ns')
            log_text.config(yscrollcommand=scrollbar.set)
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
            button_frame.grid_columnconfigure(0, weight=1)
            ttk.Button(button_frame, text='Copy to Clipboard', command=lambda: self.root.clipboard_append(log_text.get('1.0', tk.END))).grid(row=0, column=0)
            ttk.Button(button_frame, text='Close', command=log_window.destroy).grid(row=0, column=1)
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')
        else:
            messagebox.showerror('Error', 'Latest log file not found.')

    def open_full_log(self):
        log_path = os.path.join(self.app_data_dir, 'fulllatestlog.txt')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            log_window = tk.Toplevel(self.root)
            log_window.title('Full Buoy Log')
            log_window.geometry('800x600')
            log_window.configure(background=self.dark_mode_colors['bg'])
            icon_path = get_resource_path('images/icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)
            main_frame = ttk.Frame(log_window)
            main_frame.pack(expand=True, fill='both', padx=5, pady=5)
            main_frame.grid_columnconfigure(0, weight=1)
            main_frame.grid_rowconfigure(0, weight=1)
            text_frame = ttk.Frame(main_frame)
            text_frame.grid(row=0, column=0, sticky='nsew')
            text_frame.grid_columnconfigure(0, weight=1)
            text_frame.grid_rowconfigure(0, weight=1)
            log_text = tk.Text(text_frame, wrap=tk.NONE, font=('Consolas', 10), bg=self.dark_mode_colors['bg'], fg=self.dark_mode_colors['fg'])
            log_text.grid(row=0, column=0, sticky='nsew')
            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=log_text.yview)
            scrollbar.grid(row=0, column=1, sticky='ns')
            log_text.config(yscrollcommand=scrollbar.set)
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
            button_frame.grid_columnconfigure(0, weight=1)
            ttk.Button(button_frame, text='Copy to Clipboard', command=lambda: self.root.clipboard_append(log_text.get('1.0', tk.END))).grid(row=0, column=0)
            ttk.Button(button_frame, text='Close', command=log_window.destroy).grid(row=0, column=1)
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')
        else:
            messagebox.showerror('Error', 'Full log file not found.')

    def check_for_fresh_update(self):
        current_version = version.parse(get_version())
        if (last_update_version := self.settings.get('last_update_version')):
            last_update_version = version.parse(last_update_version)
            if current_version > last_update_version:
                messagebox.showinfo('Update Complete', f'Buoy has been updated to version {current_version}.')
                self.settings['last_update_version'] = str(current_version)
                self.save_settings()
        else:
            self.settings['last_update_version'] = str(current_version)
            self.save_settings()

    def uninstall_gdweave(self):
        if not self.settings.get('game_path'):
            messagebox.showerror('Error', 'Game path not set. Please set the game path first.')
            return
        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        winmm_path = os.path.join(self.settings['game_path'], 'winmm.dll')
        if not os.path.exists(gdweave_path) and (not os.path.exists(winmm_path)):
            messagebox.showinfo('Info', 'GDWeave is not installed.')
            return
        if messagebox.askyesno('Confirm Uninstall', 'Are you sure you want to uninstall GDWeave? This will remove the GDWeave folder, all mods within it, and the winmm.dll file from your game directory.'):
            try:
                shutil.rmtree(gdweave_path, ignore_errors=True)
                if os.path.exists(winmm_path):
                    os.remove(winmm_path)
                remaining_files = []
                if os.path.exists(gdweave_path):
                    remaining_files.append('GDWeave folder')
                if os.path.exists(winmm_path):
                    remaining_files.append('winmm.dll')
                if remaining_files:
                    warning_message = f"Some files could not be deleted: {', '.join(remaining_files)}. This may be due to insufficient permissions or open programs. Please close all related programs and try again."
                    messagebox.showwarning('Partial Uninstall', warning_message)
                    self.set_status('GDWeave partially uninstalled')
                else:
                    self.settings['gdweave_version'] = None
                    self.save_settings()
                    self.set_status('GDWeave uninstalled successfully')
                    messagebox.showinfo('Success', 'GDWeave has been uninstalled successfully.')
                self.update_setup_status()
                logging.info('GDWeave uninstallation process completed.')
            except Exception as e:
                error_message = f'Failed to uninstall GDWeave: {str(e)}'
                self.set_status(error_message)
                messagebox.showerror('Error', error_message)

    def create_main_ui(self):
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        self.create_mod_manager_tab()
        self.create_modpacks_tab()
        # self.create_server_browser_tab() # WIP
        self.create_game_manager_tab()
        self.create_buoy_setup_tab()
        self.create_settings_tab()
        self.copy_existing_gdweave_mods()
        self.load_available_mods()
        self.refresh_mod_lists()

    def create_mod_manager_tab(self):
        mod_manager_frame = ttk.Frame(self.notebook)
        self.notebook.add(mod_manager_frame, text='Mod Manager')
        mod_manager_frame.grid_columnconfigure(0, weight=1)
        mod_manager_frame.grid_columnconfigure(1, weight=0)
        mod_manager_frame.grid_columnconfigure(2, weight=1)
        mod_manager_frame.grid_rowconfigure(0, weight=3)
        mod_manager_frame.grid_rowconfigure(1, weight=1)
        available_frame = ttk.LabelFrame(mod_manager_frame, text='Thunderstore Mods (0)')
        self.available_frame = available_frame
        available_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        available_frame.grid_columnconfigure(0, weight=1)
        available_frame.grid_rowconfigure(0, weight=0)
        available_frame.grid_rowconfigure(1, weight=0)
        available_frame.grid_rowconfigure(2, weight=1)
        search_frame = ttk.Frame(available_frame)
        search_frame.grid(row=0, column=0, sticky='ew', padx=2, pady=2)
        search_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(search_frame, text='Search:').grid(row=0, column=0, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda name, index, mode: self.filter_available_mods())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky='ew', padx=5)
        self.advanced_filters_visible = tk.BooleanVar(value=False)
        ttk.Button(search_frame, text='Advanced Filters', command=self.toggle_advanced_filters).grid(row=0, column=2, padx=5)
        self.filter_frame = ttk.LabelFrame(available_frame, text='Advanced Filters')
        category_frame = ttk.Frame(self.filter_frame)
        category_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(category_frame, text='Category:').pack(side='left', padx=5)
        self.available_category = ttk.Combobox(category_frame, state='readonly')
        self.available_category.pack(side='left', fill='x', expand=True, padx=5)
        self.available_category.bind('<<ComboboxSelected>>', lambda e: self.filter_available_mods())
        sort_frame = ttk.Frame(self.filter_frame)
        sort_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(sort_frame, text='Sort:').pack(side='left', padx=5)
        self.sort_method = ttk.Combobox(sort_frame, state='readonly', values=['Last Updated', 'Most Downloads', 'Most Likes', 'Name (A-Z)', 'Name (Z-A)'], textvariable=self.available_sort_by)
        self.sort_method.pack(side='left', fill='x', expand=True, padx=5)
        self.sort_method.bind('<<ComboboxSelected>>', lambda e: (self.filter_available_mods(), self.save_sort_preferences()))
        toggle_frame = ttk.Frame(self.filter_frame)
        toggle_frame.pack(fill='x', padx=5, pady=2)
        ttk.Checkbutton(toggle_frame, text='Show NSFW', variable=self.show_nsfw, command=lambda: self.handle_filter_toggle('nsfw')).pack(side='left', padx=5)
        ttk.Checkbutton(toggle_frame, text='Show Deprecated', variable=self.show_deprecated, command=lambda: self.handle_filter_toggle('deprecated')).pack(side='left', padx=5)
        self.available_listbox = tk.Listbox(available_frame, width=30, height=15, selectmode=tk.EXTENDED)
        self.available_listbox.grid(row=2, column=0, pady=(2, 2), padx=2, sticky='nsew')
        self.available_listbox.bind('<<ListboxSelect>>', self.on_available_listbox_select)
        self.available_listbox.bind('<Button-3>', self.show_context_menu)
        scrollbar = ttk.Scrollbar(available_frame, orient='vertical', command=self.available_listbox.yview)
        scrollbar.grid(row=2, column=1, sticky='ns')
        self.available_listbox.configure(yscrollcommand=scrollbar.set)
        action_frame = ttk.Frame(mod_manager_frame)
        action_frame.grid(row=0, column=1, padx=5, pady=5, sticky='ns')
        action_frame.grid_columnconfigure(0, weight=1)
        self.game_management_frame = ttk.LabelFrame(action_frame, text='Launch Game')
        self.game_management_frame.grid(row=1, column=0, pady=5, padx=5, sticky='ew')
        self.game_management_frame.grid_columnconfigure(0, weight=1)
        self.game_management_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(self.game_management_frame, text='Modded', command=self.launch_modded).grid(row=0, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(self.game_management_frame, text='Vanilla', command=self.launch_vanilla).grid(row=0, column=1, pady=2, padx=2, sticky='ew')
        self.mod_management_frame = ttk.LabelFrame(action_frame, text='Mod Management')
        self.mod_management_frame.grid(row=2, column=0, pady=5, padx=5, sticky='ew')
        self.mod_management_frame.grid_columnconfigure(0, weight=1)
        self.mod_management_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(self.mod_management_frame, text='Install', command=self.install_mod).grid(row=0, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(self.mod_management_frame, text='Uninstall', command=self.uninstall_mod).grid(row=0, column=1, pady=2, padx=2, sticky='ew')
        ttk.Button(self.mod_management_frame, text='Enable', command=self.enable_mod).grid(row=1, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(self.mod_management_frame, text='Disable', command=self.disable_mod).grid(row=1, column=1, pady=2, padx=2, sticky='ew')
        ttk.Button(self.mod_management_frame, text='Edit Config', command=self.edit_mod_config).grid(row=2, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(self.mod_management_frame, text='Version', command=self.show_version_selection).grid(row=2, column=1, pady=2, padx=2, sticky='ew')
        misc_frame = ttk.LabelFrame(action_frame, text='Misc')
        misc_frame.grid(row=3, column=0, pady=5, padx=5, sticky='ew')
        misc_frame.grid_columnconfigure(0, weight=1)
        ttk.Button(misc_frame, text='Import .zip Mods', command=self.import_zip_mod).grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        ttk.Button(misc_frame, text='Refresh Mods', command=self.refresh_all_mods).grid(row=1, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(misc_frame, text='Check for Mod Updates', command=self.check_for_updates).grid(row=2, column=0, pady=2, padx=2, sticky='ew')
        ttk.Button(misc_frame, text='Join Discord', command=lambda: webbrowser.open('https://discord.gg/7HdZJZbkhw')).grid(row=3, column=0, padx=2, pady=2, sticky='ew')
        installed_frame = ttk.LabelFrame(mod_manager_frame, text='Installed Mods (0)')
        self.installed_frame = installed_frame
        installed_frame.grid(row=0, column=2, padx=5, pady=5, sticky='nsew')
        installed_search_frame = ttk.Frame(installed_frame)
        installed_search_frame.grid(row=0, column=0, sticky='ew', padx=2, pady=2)
        installed_search_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(installed_search_frame, text='Search:').grid(row=0, column=0, padx=5)
        self.installed_search_var = tk.StringVar()
        self.installed_search_var.trace('w', lambda name, index, mode: self.filter_installed_mods())
        installed_search_entry = ttk.Entry(installed_search_frame, textvariable=self.installed_search_var)
        installed_search_entry.grid(row=0, column=1, sticky='ew', padx=5)
        self.installed_filters_visible = tk.BooleanVar(value=False)
        ttk.Button(installed_search_frame, text='Advanced Filters', command=self.toggle_installed_filters).grid(row=0, column=2, padx=5)
        self.installed_filter_frame = ttk.LabelFrame(installed_frame, text='Advanced Filters')
        installed_filter_frame = ttk.Frame(self.installed_filter_frame)
        installed_filter_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(installed_filter_frame, text='Category:').pack(side='left', padx=5)
        self.installed_category = ttk.Combobox(installed_filter_frame, state='readonly')
        self.installed_category.pack(side='left', fill='x', expand=True, padx=5)
        self.installed_category.bind('<<ComboboxSelected>>', self.filter_installed_mods)
        installed_sort_frame = ttk.Frame(self.installed_filter_frame)
        installed_sort_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(installed_sort_frame, text='Sort:').pack(side='left', padx=5)
        self.installed_sort_method = ttk.Combobox(installed_sort_frame, state='readonly', values=['Name (A-Z)', 'Name (Z-A)', 'Recently Updated', 'Recently Installed'], textvariable=self.installed_sort_by)
        self.installed_sort_method.pack(side='left', fill='x', expand=True, padx=5)
        self.installed_sort_method.bind('<<ComboboxSelected>>', lambda e: (self.filter_installed_mods(), self.save_sort_preferences()))
        self.hide_third_party = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.installed_filter_frame, text='Hide 3rd Party', variable=self.hide_third_party, command=self.filter_installed_mods).pack(fill='x', padx=5, pady=2)
        self.installed_listbox = tk.Listbox(installed_frame, width=30, height=15, selectmode=tk.EXTENDED)
        installed_scrollbar = ttk.Scrollbar(installed_frame, orient='vertical', command=self.installed_listbox.yview)
        self.installed_listbox.configure(yscrollcommand=installed_scrollbar.set)
        self.installed_listbox.grid(row=2, column=0, pady=2, padx=2, sticky='nsew')
        installed_scrollbar.grid(row=2, column=1, pady=2, sticky='ns')
        self.installed_listbox.bind('<<ListboxSelect>>', lambda e: (self.update_mod_details(e), self.update_button_states()))
        self.installed_listbox.bind('<Button-3>', self.show_context_menu)
        installed_frame.grid_columnconfigure(0, weight=1)
        installed_frame.grid_rowconfigure(2, weight=1)
        self.mod_details_frame = ttk.LabelFrame(mod_manager_frame, text='Mod Details')
        self.mod_details_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='nsew')
        self.mod_image = ttk.Label(self.mod_details_frame)
        self.mod_image.grid(row=0, column=0, padx=5, pady=5, sticky='nw')
        self.mod_details = tk.Text(self.mod_details_frame, wrap=tk.WORD, height=12, state='disabled')
        self.mod_details.grid(row=0, column=1, pady=2, padx=2, sticky='nsew')
        self.mod_details_frame.grid_columnconfigure(1, weight=1)
        self.mod_details_frame.grid_rowconfigure(0, weight=1)
        self.update_button_states()

    def create_modpacks_tab(self):
        modpacks_frame = ttk.Frame(self.notebook)
        self.notebook.add(modpacks_frame, text='Mod Profiles')
        modpacks_frame.grid_columnconfigure(0, weight=1)
        modpacks_frame.grid_rowconfigure(2, weight=1)

        title_label = ttk.Label(modpacks_frame, text='Mod Profiles', font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky='w')

        subtitle_label = ttk.Label(modpacks_frame, text='Create, import, export, and manage mod profiles', font=('Helvetica', 10, 'italic'))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky='w')

        panels_container = ttk.Frame(modpacks_frame)
        panels_container.grid(row=2, column=0, sticky='nsew', pady=5)
        panels_container.grid_columnconfigure(0, weight=1)
        panels_container.grid_columnconfigure(1, weight=1)
        panels_container.grid_rowconfigure(0, weight=1)

        left_frame = ttk.LabelFrame(panels_container, text='Available Mod Profiles')
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(5, 2.5))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        self.modpacks_listbox = tk.Listbox(left_frame, width=45)
        modpacks_scrollbar = ttk.Scrollbar(left_frame, orient='vertical', command=self.modpacks_listbox.yview)
        self.modpacks_listbox.configure(yscrollcommand=modpacks_scrollbar.set)
        self.modpacks_listbox.grid(row=1, column=0, sticky='nsew', padx=(5, 0), pady=5)
        modpacks_scrollbar.grid(row=1, column=1, sticky='ns', pady=5, padx=(0, 5))
        self.modpacks_listbox.bind('<<ListboxSelect>>', self.on_modpack_select)

        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=5)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(buttons_frame, text='Create', command=self.create_modpack_window).grid(row=0, column=0, padx=2, pady=2, sticky='ew')
        ttk.Button(buttons_frame, text='Import', command=self.import_modpack).grid(row=0, column=1, padx=2, pady=2, sticky='ew')
        ttk.Button(buttons_frame, text='Import JSON', command=self.import_json_modpack).grid(row=1, column=0, padx=2, pady=2, sticky='ew')
        ttk.Button(buttons_frame, text='Delete', command=self.remove_modpack).grid(row=1, column=1, padx=2, pady=2, sticky='ew')
        ttk.Button(buttons_frame, text='Apply Mod Profile', command=self.apply_modpack).grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky='nsew')
        buttons_frame.grid_rowconfigure(2, weight=1)
        right_frame = ttk.LabelFrame(panels_container, text='Mod Profile Details')
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(2.5, 5))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)

        self.modpack_details = tk.Text(right_frame, wrap=tk.WORD)
        details_scrollbar = ttk.Scrollbar(right_frame, orient='vertical', command=self.modpack_details.yview)
        self.modpack_details.configure(yscrollcommand=details_scrollbar.set)
        self.modpack_details.grid(row=0, column=0, sticky='nsew', padx=(5, 0), pady=5)
        details_scrollbar.grid(row=0, column=1, sticky='ns', pady=5, padx=(0, 5))
        self.modpack_details.config(state='disabled')

        self.modpacks_dir = os.path.join(self.app_data_dir, 'modpacks')
        os.makedirs(self.modpacks_dir, exist_ok=True)
        self.refresh_modpacks_list()

    def import_json_modpack(self):
        file_path = filedialog.askopenfilename(filetypes=[('JSON files', '*.json')])
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                modpack_info = json.load(f)
            required_fields = ['name', 'author', 'description', 'mods']
            if not all(field in modpack_info for field in required_fields):
                raise Exception('Invalid mod profile format')
            modpack_path = os.path.join(self.modpacks_dir, f"{modpack_info['name']}.json")
            if os.path.exists(modpack_path):
                if not messagebox.askyesno('Mod Profile Exists', 'Overwrite existing mod profile?'):
                    return
            with open(modpack_path, 'w') as outfile:
                json.dump(modpack_info, outfile, indent=4)
            self.refresh_modpacks_list()
            self.modpacks_listbox.selection_set(self.modpacks_listbox.get(0, tk.END).index(modpack_info['name']))
            self.on_modpack_select(None)
            if messagebox.askyesno('Import Success', 'Apply mod profile now?'):
                self.apply_imported_modpack(modpack_info)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to import mod profile: {str(e)}')
            self.set_status(f'Failed to import mod profile: {str(e)}')

    def apply_imported_modpack(self, modpack_info):
        try:
            for mod in self.installed_mods:
                mod['enabled'] = False
                self.save_mod_info(mod)

            for mod_entry in modpack_info['mods']:
                mod_id = mod_entry['id']
                existing_mod = next((mod for mod in self.installed_mods if mod['id'] == mod_id), None)

                if existing_mod:
                    if existing_mod.get('version') != mod_entry.get('version'):
                        if mod_entry.get('thunderstore_id'):
                            available_mod = next((mod for mod in self.available_mods if mod['thunderstore_id'] == mod_entry['thunderstore_id']), None)
                            if available_mod:
                                self.uninstall_mod_files(existing_mod)
                                temp_mod = available_mod.copy()
                                temp_mod.update({'version': mod_entry['version'], 'id': mod_id, 'third_party': mod_entry.get('third_party', False)})
                                self.download_and_install_mod(temp_mod)
                                continue
                    existing_mod['enabled'] = True
                    self.save_mod_info(existing_mod)
                elif mod_entry.get('thunderstore_id'):
                    available_mod = next((mod for mod in self.available_mods if mod['thunderstore_id'] == mod_entry['thunderstore_id']), None)
                    if available_mod:
                        temp_mod = available_mod.copy()
                        temp_mod.update({'version': mod_entry['version'], 'id': mod_id, 'third_party': mod_entry.get('third_party', False)})
                        self.download_and_install_mod(temp_mod)

            self.refresh_mod_lists()
            messagebox.showinfo('Success', f"Mod profile '{modpack_info['name']}' applied successfully!")
            self.set_status(f"Applied mod profile: {modpack_info['name']}")

        except Exception as e:
            error_message = f"Failed to apply mod profile: {str(e)}"
            messagebox.showerror('Error', error_message)
            self.set_status(error_message)

    def create_modpack_window(self):
        modpack_window = tk.Toplevel(self.root)
        modpack_window.title('Create Mod Profile')
        modpack_window.geometry('800x600')
        modpack_window.configure(bg='#2b2b2b')
        icon_path = get_resource_path('images/icon.ico')
        if os.path.exists(icon_path):
            modpack_window.iconbitmap(icon_path)
        modpack_window.grid_columnconfigure(0, weight=1)
        modpack_window.grid_columnconfigure(1, weight=1)
        modpack_window.grid_rowconfigure(1, weight=1)
        info_frame = ttk.LabelFrame(modpack_window, text='Mod Profile Information')
        info_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        ttk.Label(info_frame, text='Name:').grid(row=0, column=0, padx=5, pady=5)
        name_entry = ttk.Entry(info_frame)
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Label(info_frame, text='Author:').grid(row=1, column=0, padx=5, pady=5)
        author_entry = ttk.Entry(info_frame)
        author_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ttk.Label(info_frame, text='Description:').grid(row=2, column=0, padx=5, pady=5)
        description_text = tk.Text(info_frame, height=3, bg='#2b2b2b', fg='white', insertbackground='white')
        description_text.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        ttk.Label(info_frame, text='Pastebin API Key:').grid(row=3, column=0, padx=5, pady=5)
        pastebin_api_key_entry = ttk.Entry(info_frame, show='*')
        pastebin_api_key_entry.grid(row=3, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(info_frame, text='Get API Key', command=lambda: webbrowser.open('https://pastebin.com/doc_api')).grid(row=4, column=1, padx=5, pady=5)
        installed_frame = ttk.LabelFrame(modpack_window, text='Installed Mods')
        installed_frame.grid(row=1, column=0, padx=5, pady=5, sticky='nsew')
        installed_listbox = tk.Listbox(installed_frame, selectmode=tk.EXTENDED, bg='#2b2b2b', fg='white', selectbackground='grey', selectforeground='#2b2b2b')
        installed_listbox.pack(fill='both', expand=True, padx=5, pady=5)
        modpack_frame = ttk.LabelFrame(modpack_window, text='Profile Mods')
        modpack_frame.grid(row=1, column=1, padx=5, pady=5, sticky='nsew')
        modpack_listbox = tk.Listbox(modpack_frame, selectmode=tk.EXTENDED, bg='#2b2b2b', fg='white', selectbackground='grey', selectforeground='#2b2b2b')
        modpack_listbox.pack(fill='both', expand=True, padx=5, pady=5)
        for mod in self.installed_mods:
            if not mod.get('third_party', False):
                installed_listbox.insert(tk.END, mod['title'])

        def add_enabled_mods_to_modpack_list():
            enabled_mods = [mod['title'] for mod in self.installed_mods if mod.get('enabled', False)]
            for mod in enabled_mods:
                if mod not in modpack_listbox.get(0, tk.END):
                    modpack_listbox.insert(tk.END, mod)

        def add_to_modpack():
            selections = installed_listbox.curselection()
            for index in selections:
                mod_name = installed_listbox.get(index)
                if mod_name not in modpack_listbox.get(0, tk.END):
                    modpack_listbox.insert(tk.END, mod_name)

        def remove_from_modpack():
            selections = modpack_listbox.curselection()
            for index in reversed(selections):
                modpack_listbox.delete(index)

        def export_modpack():
            if not name_entry.get().strip() or not author_entry.get().strip():
                messagebox.showerror('Error', 'Please enter a name and author for the modpack.')
                return
            modpack_info = {
                'name': name_entry.get().strip(),
                'author': author_entry.get().strip(),
                'description': description_text.get('1.0', tk.END).strip(),
                'mods': [{'id': mod['id'], 'title': mod['title'], 'version': mod.get('version', 'Unknown'), 'thunderstore_id': mod.get('thunderstore_id')} for mod in self.installed_mods if mod['title'] in modpack_listbox.get(0, tk.END) and (not mod.get('third_party', False))],
                'created': datetime.now().isoformat()
            }
            json_data = json.dumps(modpack_info, indent=2)
            file_path = filedialog.asksaveasfilename(title='Export Modpack as JSON', defaultextension='.json', filetypes=[('JSON files', '*.json')])
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(json_data)
                messagebox.showinfo('Success', 'Modpack exported successfully!')

        def save_modpack():
            name = name_entry.get().strip()
            author = author_entry.get().strip()
            api_dev_key = pastebin_api_key_entry.get()
            description = description_text.get('1.0', tk.END).strip()
            if not name:
                messagebox.showerror('Error', 'Please enter a mod profile name')
                return
            modpack_mods = list(modpack_listbox.get(0, tk.END))
            if not modpack_mods:
                messagebox.showerror('Error', 'Please add at least one mod to the mod profile')
                return
            modpack_info = {'name': name, 'author': author, 'description': description, 'created': datetime.now().isoformat(), 'mods': [{'id': mod['id'], 'title': mod['title'], 'version': mod.get('version', 'Unknown'), 'thunderstore_id': mod.get('thunderstore_id')} for mod in self.installed_mods if mod['title'] in modpack_mods and (not mod.get('third_party', False))]}
            try:
                modpack_filename = f'{name}.json'
                modpack_path = os.path.join(self.modpacks_dir, modpack_filename)
                existing_paste_id = None
                if os.path.exists(modpack_path):
                    if not messagebox.askyesno('Mod Profile Exists', 'A mod profile with this name already exists. Do you want to overwrite it?'):
                        return
                    try:
                        with open(modpack_path, 'r') as f:
                            existing_data = json.load(f)
                            existing_paste_id = existing_data.get('paste_id')
                    except:
                        pass
                json_data = json.dumps(modpack_info, indent=2)
                api_url = 'https://pastebin.com/api/api_post.php'
                data = {'api_dev_key': api_dev_key, 'api_option': 'paste', 'api_paste_code': json_data, 'api_paste_name': f'Buoy Mod Profile - {name}', 'api_paste_format': 'json', 'api_paste_private': '0', 'api_paste_expire_date': 'N'}
                response = requests.post(api_url, data=data)
                if response.status_code == 200 and response.text.startswith('https://pastebin.com/'):
                    paste_id = response.text.split('/')[-1]
                    modpack_info['paste_id'] = paste_id
                    with open(modpack_path, 'w') as f:
                        json.dump(modpack_info, f, indent=2)
                    if existing_paste_id:
                        message = f'Mod profile updated successfully!\nPrevious share code: {existing_paste_id}\nNew share code: {paste_id}\nThe new code has been copied to your clipboard.'
                    else:
                        message = f'Mod profile created successfully!\nShare this code with others: {paste_id}\nIt has also been copied to your clipboard.'
                    messagebox.showinfo('Success', message)
                    self.root.clipboard_clear()
                    self.root.clipboard_append(paste_id)
                    self.root.update()
                    self.refresh_modpacks_list()
                    for i in range(self.modpacks_listbox.size()):
                        if self.modpacks_listbox.get(i) == name:
                            self.modpacks_listbox.selection_clear(0, tk.END)
                            self.modpacks_listbox.selection_set(i)
                            self.modpacks_listbox.see(i)
                            self.on_modpack_select(None)
                            break
                    modpack_window.destroy()
                else:
                    raise Exception(f'Failed to create paste: {response.text}')
            except Exception as e:
                error_message = f'Failed to create mod profile: {str(e)}'
                messagebox.showerror('Error', error_message)
        buttons_frame = ttk.Frame(modpack_window)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=5)
        ttk.Button(buttons_frame, text='Add Selected', command=add_to_modpack).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Remove Selected', command=remove_from_modpack).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Add Enabled Mods', command=add_enabled_mods_to_modpack_list).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Export as JSON', command=export_modpack).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Save Profile', command=save_modpack).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Cancel', command=modpack_window.destroy).pack(side='left', padx=5)

    def import_modpack(self):
        paste_id = simpledialog.askstring('Import Mod Profile', 'Enter the mod profile code:')
        if not paste_id:
            return
        try:
            response = requests.get(f'https://pastebin.com/raw/{paste_id}')
            if response.status_code != 200:
                raise Exception('Failed to fetch mod profile data')
            modpack_info = json.loads(response.text)
            required_fields = ['name', 'author', 'description', 'mods']
            if not all((field in modpack_info for field in required_fields)):
                raise Exception('Invalid mod profile format')
            modpack_info['paste_id'] = paste_id
            modpack_filename = f"{modpack_info['name']}.json"
            modpack_path = os.path.join(self.modpacks_dir, modpack_filename)
            if os.path.exists(modpack_path):
                if not messagebox.askyesno('Mod Profile Exists', 'A mod profile with this name already exists. Do you want to overwrite it?'):
                    return
            with open(modpack_path, 'w') as f:
                json.dump(modpack_info, f, indent=2)
            self.refresh_modpacks_list()
            for i in range(self.modpacks_listbox.size()):
                if self.modpacks_listbox.get(i) == modpack_info['name']:
                    self.modpacks_listbox.selection_clear(0, tk.END)
                    self.modpacks_listbox.selection_set(i)
                    self.modpacks_listbox.see(i)
                    self.on_modpack_select(None)
                    break
            if messagebox.askyesno('Import Success', 'Mod profile imported successfully! Would you like to apply it now?'):
                self.apply_modpack()
        except Exception as e:
            error_message = f'Failed to import mod profile: {str(e)}'
            messagebox.showerror('Error', error_message)
            self.set_status(error_message)

    def refresh_modpacks_list(self):
        self.modpacks_listbox.delete(0, tk.END)
        for file in os.listdir(self.modpacks_dir):
            if file.endswith('.json'):
                self.modpacks_listbox.insert(tk.END, file[:-5])

    def on_modpack_select(self, event):
        selected = self.modpacks_listbox.curselection()
        if not selected:
            return
        modpack_name = self.modpacks_listbox.get(selected[0])
        modpack_path = os.path.join(self.modpacks_dir, f'{modpack_name}.json')
        try:
            with open(modpack_path, 'r') as f:
                modpack_info = json.load(f)
            self.modpack_details.config(state='normal')
            self.modpack_details.delete(1.0, tk.END)
            self.modpack_details.insert(tk.END, f"Name: {modpack_info['name']}\n")
            self.modpack_details.insert(tk.END, f"Author: {modpack_info['author']}\n")
            created_date = datetime.fromisoformat(modpack_info['created'])
            formatted_date = created_date.strftime('%I:%M%p %d/%m/%Y')
            self.modpack_details.insert(tk.END, f'Created: {formatted_date}\n')
            if 'paste_id' in modpack_info:
                self.modpack_details.insert(tk.END, f"Share Code: {modpack_info['paste_id']}\n")
            self.modpack_details.insert(tk.END, f"\nDescription:\n{modpack_info['description']}\n\n")
            self.modpack_details.insert(tk.END, 'Included Mods:\n')
            for mod in modpack_info['mods']:
                self.modpack_details.insert(tk.END, f"• {mod['title']} v{mod['version']}\n")
            self.modpack_details.config(state='disabled')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load mod profile details: {str(e)}')

    def apply_modpack(self):
        selected = self.modpacks_listbox.curselection()
        if not selected:
            messagebox.showerror('Error', 'Please select a mod profile to apply.')
            return
        modpack_name = self.modpacks_listbox.get(selected[0])
        modpack_path = os.path.join(self.modpacks_dir, f'{modpack_name}.json')
        if messagebox.askyesno('Confirm Apply', 'Applying this mod profile will disable all current mods and enable only the mods in the mod profile. Continue?'):
            try:
                with open(modpack_path) as f:
                    modpack_info = json.load(f)
                for mod in self.installed_mods:
                    mod['enabled'] = False
                    self.save_mod_info(mod)
                for mod_entry in modpack_info['mods']:
                    mod_id = mod_entry['id']
                    existing_mod = next((mod for mod in self.installed_mods if mod['id'] == mod_id), None)
                    if existing_mod:
                        if existing_mod.get('version') != mod_entry.get('version'):
                            if mod_entry.get('thunderstore_id'):
                                available_mod = next((mod for mod in self.available_mods if mod['thunderstore_id'] == mod_entry['thunderstore_id']), None)
                                if available_mod:
                                    self.uninstall_mod_files(existing_mod)
                                    temp_mod = available_mod.copy()
                                    temp_mod.update({'version': mod_entry['version'], 'id': mod_id, 'third_party': mod_entry.get('third_party', False)})
                                    self.download_and_install_mod(temp_mod)
                                    continue
                        existing_mod['enabled'] = True
                        self.save_mod_info(existing_mod)
                    elif mod_entry.get('thunderstore_id'):
                        available_mod = next((mod for mod in self.available_mods if mod['thunderstore_id'] == mod_entry['thunderstore_id']), None)
                        if available_mod:
                            temp_mod = available_mod.copy()
                            temp_mod.update({'version': mod_entry['version'], 'id': mod_id, 'third_party': mod_entry.get('third_party', False)})
                            self.download_and_install_mod(temp_mod)
                self.refresh_mod_lists()
                messagebox.showinfo('Success', f"Mod profile '{modpack_name}' applied successfully!")
                self.set_status(f'Applied mod profile: {modpack_name}')
            except Exception as e:
                error_message = f'Failed to apply mod profile: {str(e)}'
                messagebox.showerror('Error', error_message)
                self.set_status(error_message)

    def save_mod_info(self, mod):
        """Saves the mod information to its mod_info.json file"""
        try:
            if mod.get('third_party', False):
                mod_dir = os.path.join(self.mods_dir, '3rd_party', mod['id'])
            else:
                mod_dir = os.path.join(self.mods_dir, mod['id'])
            mod_info_path = os.path.join(mod_dir, 'mod_info.json')
            with open(mod_info_path, 'w') as f:
                json.dump(mod, f, indent=2)
            self.save_mod_status(mod)
        except Exception as e:
            error_message = f"Failed to save mod info for {mod.get('title', 'Unknown')}: {str(e)}"
            self.set_status(error_message)
            logging.error(error_message)

    def remove_modpack(self):
        selected = self.modpacks_listbox.curselection()
        if not selected:
            messagebox.showerror('Error', 'Please select a mod profile to remove.')
            return
        modpack_name = self.modpacks_listbox.get(selected[0])
        modpack_path = os.path.join(self.modpacks_dir, f'{modpack_name}.json')
        if messagebox.askyesno('Confirm Remove', 'Do you want to remove this mod profile?'):
            try:
                os.remove(modpack_path)
                self.refresh_mod_lists()
                self.refresh_modpacks_list()
                self.set_status(f'Removed mod profile: {modpack_name}')
            except Exception as e:
                error_message = f'Failed to remove mod profile: {str(e)}'
                messagebox.showerror('Error', error_message)
                self.set_status(error_message)

    def toggle_advanced_filters(self):
        if self.advanced_filters_visible.get():
            self.filter_frame.grid_remove()
            self.advanced_filters_visible.set(False)
        else:
            self.filter_frame.grid(row=1, column=0, sticky='ew', padx=2, pady=2)
            self.advanced_filters_visible.set(True)

    def toggle_installed_filters(self):
        if self.installed_filters_visible.get():
            self.installed_filter_frame.grid_remove()
            self.installed_filters_visible.set(False)
        else:
            self.installed_filter_frame.grid(row=1, column=0, sticky='ew', padx=2, pady=2)
            self.installed_filters_visible.set(True)

    def view_deprecated_mods_list(self):
        messagebox.showinfo('Deprecated Mods List', "This will open a new tab with the deprecated mods list. Note that these mods may be outdated, broken, or no longer work. If you download one, you'll need to import it via the 'Import ZIP' option.")
        webbrowser.open('https://notnite.github.io/webfishing-mods')

    def on_available_listbox_select(self, event):
        self.update_mod_details(event)
        self.check_selection_limit(event)
        self.update_button_states()

    def update_button_states(self):
        available_selected = bool(self.available_listbox.curselection())
        installed_selected = bool(self.installed_listbox.curselection())
        selected_mod = None
        if installed_selected:
            selected_indices = self.get_selected_installed_mod_indices()
            if selected_indices:
                selected_mod = self.filtered_installed_mods[selected_indices[0]]
        for child in self.mod_management_frame.winfo_children():
            if isinstance(child, ttk.Button):
                text = child.cget('text')
                if text == 'Install':
                    child.configure(state='normal' if available_selected else 'disabled')
                elif text == 'Edit Config':
                    has_config = selected_mod and self.mod_has_config(selected_mod)
                    child.configure(state='normal' if installed_selected and has_config else 'disabled')
                elif text in ['Uninstall', 'Enable', 'Disable']:
                    child.configure(state='normal' if installed_selected else 'disabled')
                elif text == 'Version':
                    child.configure(state='normal' if installed_selected else 'disabled')
        start_game_btn = self.game_management_frame.winfo_children()[0]
        start_game_btn.configure(state='normal' if self.check_setup() else 'disabled')

    def check_selection_limit(self, event):
        listbox = event.widget
        if listbox != self.available_listbox:
            return
        if self.mod_limit_disabled:
            return
        selected = listbox.curselection()
        actual_mods = [i for i in selected if not listbox.get(i).startswith('--')]
        if len(actual_mods) > 10:
            listbox.selection_clear(0, tk.END)
            for i in actual_mods[:10]:
                listbox.selection_set(i)
            messagebox.showwarning('Selection Limit', 'You can only select up to 10 mods for installation at once.')
        elif len(actual_mods) > 3 and (not self.multi_mod_warning_shown):
            messagebox.showwarning('Performance Warning', 'You have selected more than 3 mods for installation.\n\nThe program may become unresponsive while downloading and installing multiple mods.\n\nThis is normal and the program will recover once the installation is complete.')
            self.multi_mod_warning_shown = True

    def set_status_safe(self, message):
        if threading.current_thread() is threading.main_thread():
            self.set_status(message)
        else:
            self.root.after(0, self.set_status, message)

    def _format_timestamp(self, timestamp):
        try:
            updated_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            diff = now - updated_dt
            if diff.days > 365:
                years = diff.days // 365
                return f"{years} year{('s' if years != 1 else '')} ago"
            elif diff.days > 30:
                months = diff.days // 30
                return f"{months} month{('s' if months != 1 else '')} ago"
            elif diff.days > 0:
                return f"{diff.days} day{('s' if diff.days != 1 else '')} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{('s' if hours != 1 else '')} ago"
            else:
                minutes = diff.seconds % 3600 // 60
                return f"{minutes} minute{('s' if minutes != 1 else '')} ago"
        except Exception:
            return None

    def _show_category_details(self, category_name):
        category_name = category_name.replace('-- ', '').replace(' --', '')
        self.mod_details.config(state='normal')
        self.mod_details.delete(1.0, tk.END)
        self.mod_details.insert(tk.END, f'{category_name} Category\n\n', 'header')
        self.mod_details.tag_config('header', font=('TkDefaultFont', 10, 'bold'))
        mod_count = sum((1 for mod in self.available_mods if category_name in mod.get('categories', [])))
        self.mod_details.insert(tk.END, f"Contains {mod_count} mod{('s' if mod_count != 1 else '')}\n\n")
        if mod_count > 0:
            self.mod_details.insert(tk.END, 'Mods in this category:\n', 'subheader')
            self.mod_details.tag_config('subheader', font=('TkDefaultFont', 9, 'bold'))
            for mod in sorted(self.available_mods, key=lambda x: x['title']):
                if category_name in mod.get('categories', []):
                    self.mod_details.insert(tk.END, f"• {mod['title']} v{mod.get('version', '?')} by {mod.get('author', 'Unknown')}\n")
        self.mod_details.config(state='disabled')

    def filter_available_mods(self, event=None):
        search_text = self.search_var.get().lower()
        selected_category = self.available_category.get()
        self.available_listbox.delete(0, tk.END)
        installed_mod_titles = {mod['title'] for mod in self.installed_mods if not mod.get('third_party', False)}
        filtered_mods = []
        for mod in self.available_mods:
            if mod['title'] in installed_mod_titles:
                continue
            if 'Modpacks' in mod.get('categories', []) and selected_category != 'Modpacks':
                continue
            if search_text and not any(
                search_text in field.lower()
                for field in [
                    mod['title'], 
                    mod.get('author', ''), 
                    mod.get('description', '')
                ]
            ):
                continue
            if selected_category != 'All' and selected_category not in mod.get('categories', []):
                continue
            filtered_mods.append(mod)
        sort_method = self.sort_method.get()
        if sort_method == 'Last Updated':
            filtered_mods.sort(key=lambda x: x.get('updated_on', ''), reverse=True)
        elif sort_method == 'Most Downloads':
            filtered_mods.sort(key=lambda x: x.get('downloads', 0), reverse=True)
        elif sort_method == 'Most Likes':
            filtered_mods.sort(key=lambda x: x.get('likes', 0), reverse=True)
        elif sort_method == 'Name (A-Z)':
            filtered_mods.sort(key=lambda x: x.get('title', '').lower())
        elif sort_method == 'Name (Z-A)':
            filtered_mods.sort(key=lambda x: x.get('title', '').lower(), reverse=True)
        for mod in filtered_mods:
            display_title = self.get_display_name(mod['title'])
            self.available_listbox.insert(tk.END, display_title)


    def check_for_duplicate_mods(self):
        mod_ids = {}
        mod_titles = {}
        duplicates = []
        processed_duplicates = set()
        for mod_folder in os.listdir(self.mods_dir):
            mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
            if os.path.exists(mod_info_path):
                with open(mod_info_path, 'r') as f:
                    mod_info = json.load(f)
                    mod_id = mod_info.get('id')
                    mod_title = mod_info.get('title')
                    mod_version = mod_info.get('version', 'Unknown')
                    if mod_id:
                        if mod_id in mod_ids and mod_id not in processed_duplicates:
                            duplicates.append((mod_ids[mod_id], mod_info_path, mod_id, mod_title, mod_version))
                            processed_duplicates.add(mod_id)
                        else:
                            mod_ids[mod_id] = mod_info_path
                    if mod_title:
                        if mod_title in mod_titles and mod_title not in processed_duplicates:
                            duplicates.append((mod_titles[mod_title], mod_info_path, mod_title, mod_id, mod_version))
                            processed_duplicates.add(mod_title)
                        else:
                            mod_titles[mod_title] = mod_info_path
        third_party_mods_dir = os.path.join(self.mods_dir, '3rd_party')
        if os.path.exists(third_party_mods_dir):
            for mod_folder in os.listdir(third_party_mods_dir):
                mod_info_path = os.path.join(third_party_mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_id = mod_info.get('id')
                        mod_title = mod_info.get('title')
                        mod_version = mod_info.get('version', 'Unknown')
                        if mod_id:
                            if mod_id in mod_ids and mod_id not in processed_duplicates:
                                duplicates.append((mod_ids[mod_id], mod_info_path, mod_id, mod_title, mod_version))
                                processed_duplicates.add(mod_id)
                            else:
                                mod_ids[mod_id] = mod_info_path
                        if mod_title:
                            if mod_title in mod_titles and mod_title not in processed_duplicates:
                                duplicates.append((mod_titles[mod_title], mod_info_path, mod_title, mod_id, mod_version))
                                processed_duplicates.add(mod_title)
                            else:
                                mod_titles[mod_title] = mod_info_path
        for original, duplicate, duplicate_identifier, duplicate_title, duplicate_version in duplicates:
            original_version = 'Unknown'
            with open(original, 'r') as f:
                original_info = json.load(f)
                original_version = original_info.get('version', 'Unknown')
            if messagebox.askyesno('Duplicate Mod Found', f'Duplicate mod found: {duplicate_title} {duplicate_version} ({duplicate_identifier}) and {duplicate_title} {original_version} ({duplicate_identifier}), would you like to delete the oldest version to fix this confliction?'):
                try:
                    duplicate_folder = os.path.dirname(duplicate)
                    shutil.rmtree(duplicate_folder)
                    self.set_status(f'Removed duplicate mod: {os.path.basename(duplicate_folder)}')
                except FileNotFoundError:
                    messagebox.showerror('Error', f'The file {duplicate_folder} was already deleted.')
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to delete duplicate mod: {str(e)}')
        self.refresh_mod_lists()


    def filter_installed_mods(self, event=None):
        if not hasattr(self, 'installed_listbox'):
            return
        categories = set()
        for mod in self.installed_mods:
            categories.update(mod.get('categories', []))
        filter_values = ['All', 'Enabled', 'Disabled'] + sorted(list(categories))
        self.installed_category['values'] = filter_values
        if not self.installed_category.get():
            self.installed_category.set('All')
        if len(self.installed_mods) > 50 and (not hasattr(self, 'large_mod_list_warning_shown')) and (not self.settings.get('suppress_mod_warning', False)):
            messagebox.showinfo('Performance Warning', "You have more than 50 mods installed.\n\nHaving this many mods installed may cause significant performance issues in-game and could lead to crashes or save corruption.\n\nWhile you can continue to install more mods, it's recommended to keep your mod count under 50 for the best experience.\n\nYou can disable this warning in Settings.", icon='warning')
            self.large_mod_list_warning_shown = True
        search_text = self.installed_search_var.get().lower()
        selected_filter = self.installed_category.get()
        self.installed_listbox.delete(0, tk.END)
        self.filtered_installed_mods = []
        for mod in self.installed_mods:
            if self.hide_third_party.get() and mod.get('third_party', False):
                continue
            if search_text and search_text not in self.get_display_name(mod['title']).lower():
                continue
            if selected_filter == 'Enabled' and (not mod.get('enabled', True)):
                continue
            elif selected_filter == 'Disabled' and mod.get('enabled', True):
                continue
            elif selected_filter not in ['All', 'Enabled', 'Disabled']:
                if selected_filter not in mod.get('categories', []):
                    continue
            self.filtered_installed_mods.append(mod)
        sort_method = self.installed_sort_method.get()
        if sort_method == 'Name (A-Z)':
            self.filtered_installed_mods.sort(key=lambda x: self.get_display_name(x['title']).lower())
        elif sort_method == 'Name (Z-A)':
            self.filtered_installed_mods.sort(key=lambda x: self.get_display_name(x['title']).lower(), reverse=True)
        for mod in self.filtered_installed_mods:
            status = '✅' if mod.get('enabled', True) else '❌'
            third_party = '[3rd] ' if mod.get('third_party', False) else ''
            display_title = self.get_display_name(mod['title'])
            self.installed_listbox.insert(tk.END, f'{status} {third_party}{display_title}'.strip())

    def get_selected_installed_mod_indices(self):
        selected = self.installed_listbox.curselection()
        if not selected:
            return []
        if hasattr(self, 'installed_mod_map'):
            return [self.installed_mod_map[i] for i in selected]
        return list(selected)

    def launch_modded(self):
        """Launch the game with mods enabled"""
        if not self.check_setup():
            messagebox.showinfo('Setup Required', 'Please follow all the steps for installation in the Buoy Setup tab.')
            self.notebook.select(3)
            return
        if not self.settings.get('game_path'):
            messagebox.showerror('Error', 'Game path not set. Please set the game path first.')
            return
        try:
            game_exe = os.path.join(self.settings['game_path'], 'webfishing.exe')
            if not os.path.exists(game_exe):
                messagebox.showerror('Error', 'Game executable not found.')
                return
            subprocess.Popen([game_exe])
            self.set_status('Game launched with mods')
        except Exception as e:
            error_message = f'Failed to launch game: {str(e)}'
            messagebox.showerror('Error', error_message)
            self.set_status(error_message)

    def launch_vanilla(self):
        """Launch the game without mods"""
        if not self.check_setup():
            messagebox.showinfo('Setup Required', 'Please follow all the steps for installation in the Buoy Setup tab.')
            self.notebook.select(3)
            return
        if not self.settings.get('game_path'):
            messagebox.showerror('Error', 'Game path not set. Please set the game path first.')
            return
        try:
            game_exe = os.path.join(self.settings['game_path'], 'webfishing.exe')
            if not os.path.exists(game_exe):
                messagebox.showerror('Error', 'Game executable not found.')
                return
            subprocess.Popen([game_exe, '--gdweave-disable'])
            self.set_status('Launched game in vanilla mode')
        except Exception as e:
            error_msg = f'Failed to launch game: {str(e)}'
            messagebox.showerror('Error', error_msg)

    def create_game_manager_tab(self):
        game_manager_frame = ttk.Frame(self.notebook)
        self.notebook.add(game_manager_frame, text='Save Manager')
        game_manager_frame.grid_columnconfigure(0, weight=1)
        game_manager_frame.grid_rowconfigure(5, weight=1)
        title_label = ttk.Label(game_manager_frame, text='Save Manager', font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky='w')
        subtitle_label = ttk.Label(game_manager_frame, text='Backup and restore your game progress', font=('Helvetica', 10, 'italic'))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky='w')
        save_path = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
        save_location_frame = ttk.Frame(game_manager_frame)
        save_location_frame.grid(row=2, column=0, pady=(0, 10), padx=20, sticky='ew')
        ttk.Label(save_location_frame, text='Save folder location:').pack(side='left')
        save_path_entry = ttk.Entry(save_location_frame, width=70)
        save_path_entry.insert(0, save_path)
        save_path_entry.config(state='readonly')
        save_path_entry.pack(side='left', padx=(5, 0))
        backup_frame = ttk.LabelFrame(game_manager_frame, text='Backup Save')
        backup_frame.grid(row=4, column=0, pady=10, padx=20, sticky='ew')
        backup_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(backup_frame, text='Backup Name:').grid(row=0, column=0, pady=5, padx=5, sticky='w')
        self.backup_name_entry = ttk.Entry(backup_frame)
        self.backup_name_entry.grid(row=0, column=1, pady=5, padx=5, sticky='ew')
        ttk.Label(backup_frame, text='Save Slot:').grid(row=1, column=0, pady=5, padx=5, sticky='w')
        self.backup_slot_var = tk.IntVar()
        slot_frame = ttk.Frame(backup_frame)
        slot_frame.grid(row=1, column=1, pady=5, padx=5, sticky='w')
        available_slots = self.get_available_save_slots()
        if available_slots:
            self.backup_slot_var.set(available_slots[0])
            for slot in range(1, 5):
                if slot in available_slots:
                    ttk.Radiobutton(slot_frame, text=f'Slot {slot}', value=slot, variable=self.backup_slot_var).pack(side='left', padx=5)
        else:
            ttk.Label(slot_frame, text='No save files found', foreground='red').pack(side='left', padx=5)
        ttk.Button(backup_frame, text='Create Backup', command=self.create_backup).grid(row=0, column=2, rowspan=2, pady=5, padx=5)
        self.restore_frame = ttk.LabelFrame(game_manager_frame, text='Manage Saves')
        self.restore_frame.grid(row=5, column=0, pady=10, padx=20, sticky='nsew')
        self.restore_frame.grid_columnconfigure(0, weight=1)
        self.restore_frame.grid_rowconfigure(0, weight=1)
        self.backup_tree = ttk.Treeview(self.restore_frame, columns=('Name', 'Timestamp'), show='headings', height=10)
        self.backup_tree.heading('Name', text='Name')
        self.backup_tree.heading('Timestamp', text='Timestamp')
        self.backup_tree.column('Name', width=200)
        self.backup_tree.column('Timestamp', width=200)
        self.backup_tree.grid(row=0, column=0, pady=5, padx=5, sticky='nsew')
        scrollbar = ttk.Scrollbar(self.restore_frame, orient='vertical', command=self.backup_tree.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.backup_tree.configure(yscrollcommand=scrollbar.set)
        buttons_frame = ttk.Frame(self.restore_frame)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky='ew')
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons_frame, text='Restore Selected', command=self.restore_backup).grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Button(buttons_frame, text='Delete Selected', command=self.delete_backup).grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Button(buttons_frame, text='Refresh List', command=self.refresh_backup_list).grid(row=0, column=2, padx=5, sticky='ew')
        self.refresh_backup_list()

    def refresh_backup_list(self):
        for i in self.backup_tree.get_children():
            self.backup_tree.delete(i)
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        if os.path.exists(backup_dir):
            backups = []
            for backup in os.listdir(backup_dir):
                if backup.endswith('.save'):
                    backup_path = os.path.join(backup_dir, backup)
                    timestamp = os.path.getmtime(backup_path)
                    name_parts = backup.rsplit('_', 1)
                    if len(name_parts) == 2:
                        name = name_parts[0].replace('_', ' ')
                        try:
                            file_timestamp = float(name_parts[1].replace('.save', ''))
                            formatted_time = datetime.fromtimestamp(file_timestamp).strftime('%I:%M%p %d/%m/%Y')
                        except ValueError:
                            formatted_time = datetime.fromtimestamp(timestamp).strftime('%I:%M%p %d/%m/%Y')
                        backups.append((name, formatted_time, timestamp))
                    else:
                        backups.append((backup, 'Unknown', timestamp))
            backups.sort(key=lambda x: x[2], reverse=True)
            for name, formatted_time, _ in backups:
                self.backup_tree.insert('', 'end', values=(name, formatted_time))
        self.set_status('Backup list refreshed')

    def create_backup(self):
        backup_name = self.backup_name_entry.get().strip()
        if not backup_name:
            messagebox.showerror('Error', 'Please enter a backup name.')
            self.set_status('Backup creation failed: No name provided')
            return
        invalid_chars = '<>:"/\\|?*'
        sanitized_name = ''.join((c for c in backup_name if c not in invalid_chars))
        sanitized_name = sanitized_name[:255]
        if not sanitized_name:
            messagebox.showerror('Error', 'The backup name contains only invalid characters. Please use a different name.')
            self.set_status('Backup creation failed: Invalid name')
            return
        selected_slot = self.backup_slot_var.get()
        save_dir = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
        save_path = os.path.join(save_dir, f'webfishing_save_slot_{selected_slot - 1}.sav')
        if not os.path.exists(save_path):
            messagebox.showerror('Error', f'No save file found in slot {selected_slot}. Please create a save in-game first.')
            return
        timestamp = int(time.time())
        backup_filename = f"{sanitized_name.replace(' ', '_')}_slot{selected_slot}_{timestamp}.save"
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_filename)
        try:
            shutil.copy2(save_path, backup_path)
            messagebox.showinfo('Success', f'Backup created: {sanitized_name} (Slot {selected_slot})')
            self.set_status(f'Backup created: {sanitized_name} (Slot {selected_slot})')
            self.refresh_backup_list()
        except Exception as e:
            error_message = f'Failed to create backup: {str(e)}'
            messagebox.showerror('Error', error_message)
            self.set_status(error_message)

    def restore_backup(self):
        selected = self.backup_tree.selection()
        if not selected:
            messagebox.showerror('Error', 'Please select a backup to restore.')
            self.set_status('Backup restoration failed: No backup selected')
            return
        item = self.backup_tree.item(selected[0])
        backup_name = item['values'][0]
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        matching_backups = [f for f in os.listdir(backup_dir) if f.startswith(backup_name.replace(' ', '_')) and f.endswith('.save')]
        if not matching_backups:
            error_message = f"Backup file for '{backup_name}' not found."
            messagebox.showerror('Error', error_message)
            self.set_status(error_message)
            return
        backup_filename = matching_backups[0]
        slot_match = re.search('_slot(\\d)_', backup_filename)
        if slot_match:
            slot_num = int(slot_match.group(1))
            if not messagebox.askyesno('Confirm Restore', f'This will restore to Slot {slot_num}. Continue?'):
                return
            save_dir = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
            backup_path = os.path.join(backup_dir, backup_filename)
            save_path = os.path.join(save_dir, f'webfishing_save_slot_{slot_num - 1}.sav')
            try:
                shutil.copy2(backup_path, save_path)
                messagebox.showinfo('Success', f'Save restored to slot {slot_num}')
                self.set_status(f'Save restored to slot {slot_num}')
                self.refresh_backup_list()
            except Exception as e:
                error_message = f'Failed to restore backup: {str(e)}'
                messagebox.showerror('Error', error_message)
                self.set_status(error_message)
        else:
            dialog = tk.Toplevel(self.root)
            dialog.title('Warning - Old Save File')
            dialog.geometry('400x300')
            dialog.transient(self.root)
            dialog.grab_set()
            icon_path = get_resource_path('images/icon.ico')
            if os.path.exists(icon_path):
                dialog.iconbitmap(icon_path)
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = dialog.winfo_screenwidth() // 2 - width // 2
            y = dialog.winfo_screenheight() // 2 - height // 2
            dialog.geometry(f'{width}x{height}+{x}+{y}')
            warning_text = 'WARNING: This is an old save file from a previous version of the game.\n\nRestoring this save will:\n1. Delete ALL current save files in slots 1-4\n2. Attempt to migrate this old save to the new format\n\nThis process may fail and could potentially result in the loss of your current saves. It is highly recommended to back up your current saves before proceeding.\n\nThe game will attempt to handle the migration automatically, but there are no guarantees.'
            ttk.Label(dialog, text=warning_text, wraplength=380).pack(pady=10, padx=10)
            understood = tk.BooleanVar(value=False)
            ttk.Checkbutton(dialog, text='I understand the risks and have backed up my saves', variable=understood).pack(pady=10)

            def on_proceed():
                if not understood.get():
                    messagebox.showwarning('Acknowledgment Required', 'You must check the box to acknowledge you understand the risks.')
                    return
                dialog.destroy()
                save_dir = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
                for slot in range(4):
                    save_path = os.path.join(save_dir, f'webfishing_save_slot_{slot}.sav')
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                        except Exception as e:
                            logging.error(f'Failed to delete save file {save_path}: {e}')
                    backup_path = os.path.join(save_dir, f'webfishing_backup_save_slot_{slot}.backup')
                    if os.path.exists(backup_path):
                        try:
                            os.remove(backup_path)
                        except Exception as e:
                            logging.error(f'Failed to delete backup file {backup_path}: {e}')
                general_data_path = os.path.join(save_dir, 'webfishing_general_data.sav')
                if os.path.exists(general_data_path):
                    try:
                        os.remove(general_data_path)
                    except Exception as e:
                        logging.error(f'Failed to delete general data file: {e}')
                backup_path = os.path.join(backup_dir, backup_filename)
                migrated_save_path = os.path.join(save_dir, 'webfishing_migrated_data.save')
                try:
                    shutil.copy2(backup_path, migrated_save_path)
                    messagebox.showinfo('Success', 'Old save file has been restored. Please start the game to complete the migration process. You probably want to restart Buoy after the game starts too.')
                    self.set_status('Old save file restored - start game to complete migration')
                    self.refresh_backup_list()
                except Exception as e:
                    error_message = f'Failed to restore backup: {str(e)}'
                    messagebox.showerror('Error', error_message)
                    self.set_status(error_message)

            def on_cancel():
                dialog.destroy()
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10, padx=10, fill=tk.X)
            ttk.Button(button_frame, text='Proceed', command=on_proceed).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text='Cancel', command=on_cancel).pack(side=tk.RIGHT, padx=5)
            dialog.wait_window()

    def get_available_save_slots(self):
        save_dir = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
        available_slots = []
        for slot in range(1, 5):
            save_path = os.path.join(save_dir, f'webfishing_save_slot_{slot - 1}.sav')
            if os.path.exists(save_path):
                available_slots.append(slot)
        return available_slots

    def delete_backup(self):
        selected = self.backup_tree.selection()
        if not selected:
            messagebox.showerror('Error', 'Please select a backup to delete.')
            self.set_status('Backup deletion failed: No backup selected')
            return
        item = self.backup_tree.item(selected[0])
        backup_name = item['values'][0]
        if messagebox.askyesno('Confirm Delete', f"Are you sure you want to delete the backup '{backup_name}'?"):
            backup_dir = os.path.join(self.app_data_dir, 'save_backups')
            matching_backups = [f for f in os.listdir(backup_dir) if f.startswith(backup_name.replace(' ', '_')) and f.endswith('.save')]
            if not matching_backups:
                error_message = f"Backup file for '{backup_name}' not found."
                messagebox.showerror('Error', error_message)
                self.set_status(error_message)
                return
            backup_filename = matching_backups[0]
            backup_path = os.path.join(backup_dir, backup_filename)
            try:
                os.remove(backup_path)
                messagebox.showinfo('Success', f'Backup deleted: {backup_name}')
                self.set_status(f'Backup deleted: {backup_name}')
                self.refresh_backup_list()
            except Exception as e:
                error_message = f'Failed to delete backup: {str(e)}'
                messagebox.showerror('Error', error_message)
                self.set_status(error_message)

    def create_buoy_setup_tab(self):
        setup_frame = ttk.Frame(self.notebook)
        self.notebook.add(setup_frame, text='Buoy Setup')
        setup_frame.grid_columnconfigure(0, weight=1)
        setup_frame.grid_rowconfigure(8, weight=1)
        title_label = ttk.Label(setup_frame, text='Buoy Setup', font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky='w')
        instruction_label = ttk.Label(setup_frame, text='Complete the steps below to start using Buoy', font=('Helvetica', 10, 'italic'))
        instruction_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky='w')
        step1_frame = ttk.LabelFrame(setup_frame, text='Step 1: Set Game Installation Path')
        step1_frame.grid(row=2, column=0, pady=10, padx=20, sticky='ew')
        step1_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(step1_frame, text='Game Path:').grid(row=0, column=0, pady=5, padx=5, sticky='w')
        self.game_path_entry = ttk.Entry(step1_frame, width=40)
        self.game_path_entry.grid(row=0, column=1, pady=5, padx=5, sticky='ew')
        self.game_path_entry.insert(0, self.settings.get('game_path', ''))
        ttk.Button(step1_frame, text='Browse', command=self.browse_game_directory).grid(row=0, column=2, pady=5, padx=5)
        ttk.Button(step1_frame, text='Save Path', command=self.save_game_path).grid(row=0, column=3, pady=5, padx=5)
        self.step1_status = ttk.Label(step1_frame, text='Unverified', foreground='red', font=('Helvetica', 10, 'bold'))
        self.step1_status.grid(row=1, column=0, columnspan=4, pady=5, padx=5, sticky='w')
        step2_frame = ttk.LabelFrame(setup_frame, text='Step 2: Verify Game Installation')
        step2_frame.grid(row=3, column=0, pady=10, padx=20, sticky='ew')
        step2_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(step2_frame, text='Verify Installation', command=self.verify_installation).grid(row=0, column=0, pady=5, padx=5)
        ttk.Label(step2_frame, text='Verify that all required game files are present').grid(row=0, column=1, pady=5, padx=5, sticky='w')
        self.step2_status = ttk.Label(step2_frame, text='Unverified', foreground='red', font=('Helvetica', 10, 'bold'))
        self.step2_status.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky='w')
        step4_frame = ttk.LabelFrame(setup_frame, text='Step 3: Install Mod Loader')
        step4_frame.grid(row=4, column=0, pady=10, padx=20, sticky='ew')
        step4_frame.grid_columnconfigure(1, weight=1)
        self.gdweave_button = ttk.Button(step4_frame, text='Install GDWeave', command=self.install_gdweave)
        self.gdweave_button.grid(row=0, column=0, pady=5, padx=5)
        self.gdweave_label = ttk.Label(step4_frame, text='Install or update the GDWeave mod loader to enable mod support')
        self.gdweave_label.grid(row=0, column=1, pady=5, padx=5, sticky='w')
        self.step4_status = ttk.Label(step4_frame, text='Uninstalled', foreground='red', font=('Helvetica', 10, 'bold'))
        self.step4_status.grid(row=1, column=0, columnspan=2, pady=5, padx=5, sticky='w')
        step5_frame = ttk.LabelFrame(setup_frame, text='Step 4: Back Up Your Save Data')
        step5_frame.grid(row=5, column=0, pady=10, padx=20, sticky='ew')
        step5_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(step5_frame, text='Important: Use the Save Manager tab to create a backup of your save data before modding', foreground='red').grid(row=0, column=1, pady=5, padx=5, sticky='w')
        self.setup_status = ttk.Label(setup_frame, text='', font=('Helvetica', 12))
        self.setup_status.grid(row=6, column=0, pady=(20, 10), padx=20, sticky='w')
        self.update_setup_status()

    def check_and_install_server_mods(self, required_mods):
        """Check for required mods and offer to install missing ones"""
        missing_mods = []
        disabled_mods = []
        installed_mod_ids = {mod.get('thunderstore_id') for mod in self.installed_mods}
        for mod_id in required_mods:
            if mod_id not in installed_mod_ids:
                missing_mods.append(mod_id)
            else:
                mod = next((m for m in self.installed_mods if m.get('thunderstore_id') == mod_id), None)
                if mod and (not mod.get('enabled', True)):
                    disabled_mods.append(mod_id)
        if not missing_mods and (not disabled_mods):
            return True
        message = 'This server requires the following mods:\n\n'
        if missing_mods:
            message += 'Missing Mods (will be downloaded):\n'
            for i, mod_id in enumerate(missing_mods[:5]):
                message += f'• {mod_id}\n'
            if len(missing_mods) > 5:
                message += f'...and {len(missing_mods) - 5} more\n'
            message += '\n'
        if disabled_mods:
            message += 'Disabled Mods (will be enabled):\n'
            for i, mod_id in enumerate(disabled_mods[:5]):
                message += f'• {mod_id}\n'
            if len(disabled_mods) > 5:
                message += f'...and {len(disabled_mods) - 5} more\n'
            message += '\n'
        message += 'Would you like to proceed with the installation/enabling of these mods?'
        if not messagebox.askyesno('Mods Required', message):
            return False
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title('Installing Mods')
        progress_dialog.geometry('300x150')
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        progress_dialog.update_idletasks()
        x = progress_dialog.winfo_screenwidth() // 2 - 300 // 2
        y = progress_dialog.winfo_screenheight() // 2 - 150 // 2
        progress_dialog.geometry(f'300x150+{x}+{y}')
        label = ttk.Label(progress_dialog, text='Installing required mods...')
        label.pack(pady=20)
        progress = ttk.Progressbar(progress_dialog, mode='determinate')
        progress.pack(pady=10, padx=20, fill=tk.X)

        def install_mods():
            try:
                total_steps = len(missing_mods) + len(disabled_mods)
                current_step = 0
                for mod_id in missing_mods:
                    available_mod = next((mod for mod in self.available_mods if mod['thunderstore_id'] == mod_id), None)
                    if available_mod:
                        self.download_and_install_mod(available_mod)
                    current_step += 1
                    progress['value'] = current_step / total_steps * 100
                    progress_dialog.update()
                for mod_id in disabled_mods:
                    mod = next((m for m in self.installed_mods if m.get('thunderstore_id') == mod_id), None)
                    if mod:
                        try:
                            index = self.filtered_installed_mods.index(mod)
                            self.installed_listbox.selection_clear(0, tk.END)
                            self.installed_listbox.selection_set(index)
                            self.enable_mod()
                        except ValueError:
                            mod['enabled'] = True
                            self.save_mod_status(mod)
                            self.copy_mod_to_game(mod)
                    current_step += 1
                    progress['value'] = current_step / total_steps * 100
                    progress_dialog.update()
                progress_dialog.destroy()
                self.refresh_mod_lists()
                return True
            except Exception as e:
                messagebox.showerror('Error', f'Failed to install mods: {str(e)}')
                progress_dialog.destroy()
                return False
        result = install_mods()
        return result

    def create_settings_tab(self):
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text='Buoy Settings')
        settings_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_rowconfigure(7, weight=1)
        title_frame = ttk.Frame(settings_frame)
        title_frame.grid(row=0, column=0, pady=(20, 0), padx=20, sticky='ew')
        title_frame.grid_columnconfigure(1, weight=1)
        title_label = ttk.Label(title_frame, text='Buoy Settings', font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, sticky='w')
        subtitle_label = ttk.Label(settings_frame, text='Customize your Buoy experience', font=('Helvetica', 10, 'italic'))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky='w')
        general_frame = ttk.LabelFrame(settings_frame, text='General Settings')
        general_frame.grid(row=2, column=0, pady=10, padx=20, sticky='ew')
        general_frame.grid_columnconfigure((0, 1), weight=1)
        left_frame = ttk.Frame(general_frame)
        left_frame.grid(row=0, column=0, sticky='w', padx=5)
        self.auto_update = tk.BooleanVar(value=self.settings.get('auto_update', True))
        ttk.Checkbutton(left_frame, text='Auto-update mods', variable=self.auto_update, command=self.save_settings).grid(row=0, column=0, pady=2, sticky='w')
        self.windowed_mode = tk.BooleanVar(value=self.settings.get('windowed_mode', False))
        ttk.Checkbutton(left_frame, text='Launch in windowed mode', variable=self.windowed_mode, command=self.save_windowed_mode).grid(row=1, column=0, pady=2, sticky='w')
        right_frame = ttk.Frame(general_frame)
        right_frame.grid(row=0, column=1, sticky='w', padx=5)
        self.auto_backup = tk.BooleanVar(value=self.settings.get('auto_backup', True))
        ttk.Checkbutton(right_frame, text='Auto-backup saves on launch', variable=self.auto_backup, command=self.save_settings).grid(row=0, column=0, pady=2, sticky='w')
        self.suppress_mod_warning = tk.BooleanVar(value=self.settings.get('suppress_mod_warning', False))
        ttk.Checkbutton(right_frame, text='Suppress mod count warning', variable=self.suppress_mod_warning, command=self.save_settings).grid(row=1, column=0, pady=2, sticky='w')
        update_frame = ttk.Frame(general_frame)
        update_frame.grid(row=4, column=0, columnspan=2, pady=5, padx=5, sticky='w')
        update_frame.grid_columnconfigure(1, weight=1)
        info_frame = ttk.LabelFrame(settings_frame, text='Buoy Information')
        info_frame.grid(row=3, column=0, pady=10, padx=20, sticky='ew')
        info_frame.grid_columnconfigure((0, 1), weight=1)
        info_frame.grid_rowconfigure(2, weight=1)
        ttk.Button(info_frame, text='View Changelog', command=self.show_changelog).grid(row=2, column=0, pady=5, padx=5, sticky='nsew')
        ttk.Button(info_frame, text='View Credits', command=self.show_credits).grid(row=2, column=1, pady=5, padx=5, sticky='nsew')
        troubleshoot_frame = ttk.LabelFrame(settings_frame, text='Troubleshooting')
        troubleshoot_frame.grid(row=5, column=0, pady=10, padx=20, sticky='ew')
        troubleshoot_frame.grid_columnconfigure((0, 1, 2), weight=1)
        quick_support_frame = ttk.Frame(troubleshoot_frame)
        quick_support_frame.grid(row=0, column=0, columnspan=3, pady=(5, 10), padx=5, sticky='ew')
        quick_support_frame.grid_columnconfigure(0, weight=1)
        support_button = ttk.Button(quick_support_frame, text='Quick Support - Copy all Debug Info', command=self.copy_support_info)
        support_button.grid(row=0, column=0, sticky='ew')
        ttk.Separator(troubleshoot_frame, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)
        self.toggle_gdweave_button = ttk.Button(troubleshoot_frame, text='   ',state='disabled')
        self.toggle_gdweave_button.grid(row=2, column=0, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Clear GDWeave Mods', command=self.clear_gdweave_mods).grid(row=2, column=1, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Clear Buoy Mods', command=self.clear_buoy_mods).grid(row=2, column=2, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Open GDWeave Log', command=self.open_gdweave_log).grid(row=3, column=0, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Open Buoy Log', command=self.open_latest_log).grid(row=3, column=1, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Open Full Buoy Log', command=self.open_full_log).grid(row=3, column=2, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Open Buoy Folder', command=self.open_buoy_folder).grid(row=4, column=0, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Open GDWeave Folder', command=self.open_gdweave_folder).grid(row=4, column=1, pady=5, padx=5, sticky='ew')
        ttk.Button(troubleshoot_frame, text='Clear Temp Folder', command=self.delete_temp_files).grid(row=4, column=2, pady=5, padx=5, sticky='ew')
        self.settings_status = ttk.Label(settings_frame, text='', font=('Helvetica', 12))
        self.settings_status.grid(row=6, column=0, pady=(10, 20), padx=20, sticky='w')
        self.root.after(100, self.process_gui_queue)

    def save_windowed_mode(self):
        self.settings['windowed_mode'] = self.windowed_mode.get()
        self.save_settings()

    def generate_support_info(self):
        info = f'```\nGenerated with Buoy (v{get_version()}) Quick Support\n'
        info += '============================\nInstalled Mods:\n'
        for mod in self.installed_mods:
            third_party = ' (Third-Party)' if mod.get('third_party', False) else ''
            info += f"{mod['title']} (v{mod.get('version', 'Unknown')}) by {mod.get('author', 'Unknown')}{third_party}\n"
        info += '============================\nGDWeave Log:\n'
        gdweave_log_path = os.path.join(self.settings.get('game_path', ''), 'GDWeave', 'gdweave.log')
        if os.path.exists(gdweave_log_path):
            try:
                with open(gdweave_log_path, 'r') as f:
                    log_content = f.read().strip()
                    info += log_content if log_content else 'No log content found'
            except Exception:
                info += 'Error reading GDWeave log'
        else:
            info += 'No log found'
        info += '\n============================\nBuoy Log:\n'
        buoy_log_path = os.path.join(self.app_data_dir, 'latestlog.txt')
        if os.path.exists(buoy_log_path):
            try:
                with open(buoy_log_path, 'r') as f:
                    lines = f.readlines()[5:]
                    log_content = ''.join(lines).strip()
                    info += log_content if log_content else 'No critical errors found in Buoy log'
            except Exception:
                info += 'Error reading Buoy log'
        else:
            info += 'No log found'
        info += '\n============================\nSystem Information:\n'
        info += f'Buoy Version: v{get_version()}\n'
        info += f"GDWeave Version: {self.settings.get('gdweave_version', 'Unknown')}\n"
        info += f'OS: {platform.system()} {platform.release()}\n'
        info += f'Python: v{platform.python_version()}\n'
        info += '============================\n```'
        return info

    def copy_support_info(self):
        support_info = self.generate_support_info()
        self.root.clipboard_clear()
        self.root.clipboard_append(support_info)
        self.set_status('Support information copied to clipboard')
        messagebox.showinfo('Success', 'Support information has been copied to your clipboard.\nYou can now paste this in Discord for support.')

    def show_credits(self):
        credits_text = 'Big thank you to the following people for their contributions to Buoy!\n\nDevelopment:\n• Paws - Developer and maintainer of Buoy\n\nBuoy Supporters:\n• @.the_blue - Created Buoy icon \n\nSpecial Thanks:\n• All mod creators for their contributions\n• You for using Buoy!\n• Pyoid - Original dev of HLS!'
        messagebox.showinfo('Credits', credits_text)

    def show_changelog(self):
        try:
            if getattr(sys, 'frozen', False):
                bundle_dir = os.path.dirname(sys.executable)
            else:
                bundle_dir = os.path.dirname(os.path.abspath(__file__))
            version_file = os.path.join(bundle_dir, 'version.json')
            with open(version_file, 'r') as f:
                version_data = json.load(f)
            changelog = version_data.get('changelog', [])
            changelog_text = 'Changelog:\n\n'
            for item in changelog:
                changelog_text += f'• {item}\n\n'
            messagebox.showinfo('Changelog', changelog_text)
        except Exception as e:
            logging.error(f'Error showing changelog: {e}')
            messagebox.showerror('Error', f'Failed to load changelog: {e}')

    def create_rotating_backup(self):
        if not self.settings.get('auto_backup', True):
            return
        available_slots = self.get_available_save_slots()
        if not available_slots:
            logging.info('No save files found for automatic backup')
            return
        backup_dir = os.path.join(self.app_data_dir, 'save_backups')
        os.makedirs(backup_dir, exist_ok=True)
        auto_backups = [f for f in os.listdir(backup_dir) if f.startswith('Auto_Backup') and f.endswith('.save')]
        auto_backups.sort(key=lambda x: float(x.split('_')[-1].replace('.save', '')))
        max_backups_per_slot = 4 // len(available_slots)
        if max_backups_per_slot < 1:
            max_backups_per_slot = 1
        slot_backups = {}
        for backup in auto_backups:
            slot_match = re.search('slot(\\d)', backup)
            if slot_match:
                slot = int(slot_match.group(1))
                if slot not in slot_backups:
                    slot_backups[slot] = []
                slot_backups[slot].append(backup)
        for slot, backups in slot_backups.items():
            if not backups:
                continue
            backups.sort(key=lambda x: float(x.split('_')[-1].replace('.save', '')))
            while len(backups) >= max_backups_per_slot:
                try:
                    oldest_backup = backups[0]
                    os.remove(os.path.join(backup_dir, oldest_backup))
                    backups.pop(0)
                    logging.info(f'Removed old backup for slot {slot}: {oldest_backup}')
                except Exception as e:
                    logging.error(f'Failed to remove old backup for slot {slot}: {e}')
                    break
        timestamp = int(time.time())
        save_dir = os.path.join(os.getenv('APPDATA'), 'Godot', 'app_userdata', 'webfishing_2_newver')
        logging.info(f'Creating automatic backups in directory: {save_dir}')
        for slot in available_slots:
            save_path = os.path.join(save_dir, f'webfishing_save_slot_{slot - 1}.sav')
            if os.path.exists(save_path):
                try:
                    backup_filename = f'Auto_Backup_slot{slot}_{timestamp}.save'
                    backup_path = os.path.join(backup_dir, backup_filename)
                    logging.info(f'Attempting to create backup for slot {slot} at: {backup_path}')
                    shutil.copy2(save_path, backup_path)
                    logging.info(f'Successfully created automatic backup for slot {slot}: {backup_filename}')
                except Exception as e:
                    logging.error(f'Failed to create automatic backup for slot {slot}: {e}')
        self.set_status('Automatic backup created')
        logging.info('Automatic backup process completed')
        logging.info('Made rotating backup')

    def copy_existing_gdweave_mods(self):
        if not self.settings.get('game_path'):
            logging.info('Game path not set, skipping existing mod copy.')
            return
        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        if not os.path.exists(gdweave_mods_path):
            logging.info('GDWeave Mods folder not found, skipping existing mod copy.')
            return
        third_party_mods_dir = os.path.join(self.mods_dir, '3rd_party')
        os.makedirs(third_party_mods_dir, exist_ok=True)
        known_mod_ids = set()
        for mod_folder in os.listdir(self.mods_dir):
            mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
            if os.path.exists(mod_info_path):
                with open(mod_info_path, 'r') as f:
                    mod_info = json.load(f)
                    known_mod_ids.add(mod_info.get('id'))
        newly_installed_mods = []
        for mod_folder in os.listdir(gdweave_mods_path):
            src_mod_path = os.path.join(gdweave_mods_path, mod_folder)
            if not os.path.isdir(src_mod_path):
                logging.info(f'Skipped: {mod_folder} (not a directory)')
                continue
            manifest_path = os.path.join(src_mod_path, 'manifest.json')
            if not os.path.exists(manifest_path):
                logging.info(f'Skipped: {mod_folder} (no manifest.json found)')
                continue
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                mod_id = manifest.get('Id')
                mod_title = manifest.get('Name', mod_folder)
                mod_author = manifest.get('Author', 'Unknown')
                mod_description = manifest.get('Description', 'No description provided')
                mod_version = manifest.get('Version', 'Unknown')
                if mod_id in known_mod_ids:
                    logging.info(f'Skipped known mod: {mod_title} (ID: {mod_id})')
                    continue
                dst_mod_path = os.path.join(third_party_mods_dir, mod_id)
                if not os.path.exists(dst_mod_path):
                    shutil.copytree(src_mod_path, dst_mod_path)
                    mod_info = {'id': mod_id, 'title': mod_title, 'author': mod_author, 'description': mod_description, 'enabled': True, 'version': mod_version, 'third_party': True, 'updated_on': int(time.time())}
                    with open(os.path.join(dst_mod_path, 'mod_info.json'), 'w') as f:
                        json.dump(mod_info, f, indent=2)
                    logging.info(f'Copied third-party mod: {mod_title} (ID: {mod_id})')
                    newly_installed_mods.append(mod_info)
                else:
                    logging.info(f'Skipped existing third-party mod: {mod_title} (ID: {mod_id})')
            except Exception as e:
                logging.info(f'Error processing mod {mod_folder}: {str(e)}')
        self.installed_mods.extend(newly_installed_mods)
        self.refresh_mod_lists()

    def delete_temp_files(self):
        temp_dir = os.path.join(os.getenv('APPDATA'), 'Hook_Line_Sinker_Reborn', 'temp')
        if os.path.exists(temp_dir):
            try:
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, stat.S_IWRITE)
                        os.remove(file_path)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, stat.S_IWRITE)
                        os.rmdir(dir_path)
                os.chmod(temp_dir, stat.S_IWRITE)
                os.rmdir(temp_dir)
                logging.info(f'Successfully deleted temporary directory: {temp_dir}')
                self.set_status('Temporary files and folders deleted successfully.')
            except Exception as e:
                error_message = f'Failed to delete temporary files and folders: {str(e)}'
                logging.error(error_message)
                self.set_status(error_message)
        else:
            logging.info(f'Temporary directory does not exist: {temp_dir}')
            self.set_status('No temporary files or folders to delete.')

    def verify_dotnet(self):
        try:
            subprocess.run(['dotnet', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.set_status('.NET is installed and working correctly.')
        except Exception as e:
            error_message = 'Please install the .NET 8.0 SDK. Visit https://dotnet.microsoft.com/download'
            self.set_status(error_message)
            messagebox.showerror('Installation Error', error_message)

    def download_and_run_dotnet_installer(self):
        self.set_status('Downloading .NET installer...')
        messagebox.showinfo('Downloading .NET', 'This will download the .NET 8.0 SDK installer. Please wait 10-20 seconds.')
        if not sys.platform.startswith('win'):
            messagebox.showerror('Unsupported OS', 'Your operating system is not supported for automatic .NET installation.')
            return
        url = 'https://download.visualstudio.microsoft.com/download/pr/6224f00f-08da-4e7f-85b1-00d42c2bb3d3/b775de636b91e023574a0bbc291f705a/dotnet-sdk-8.0.403-win-x64.exe'

        def download_and_install():
            try:
                temp_dir = os.path.join(os.getenv('APPDATA'), 'Hook_line_Sinker_Reborn', 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                with requests.get(url, stream=True) as response:
                    response.raise_for_status()
                    total_size = int(response.headers.get('content-length', 0))
                    temp_file_path = os.path.join(temp_dir, 'dotnet_installer.exe')
                    with open(temp_file_path, 'wb') as temp_file:
                        downloaded_size = 0
                        chunk_size = 8192
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                                self.root.update_idletasks()
                self.set_status('Download complete.')
                subprocess.Popen([temp_file_path, '/norestart'])
                self.set_status('Installer launched. Please follow the installation prompts.')
                messagebox.showinfo('Installation Started', 'The .NET installer has been launched. Please follow the installation prompts. After installation, please restart Buoy.')
            except Exception as e:
                error_message = f'Failed to download or install .NET: {str(e)}'
                self.set_status(error_message)
                messagebox.showerror('Installation Error', error_message)
            finally:
                if 'temp_file_path' in locals():
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
        threading.Thread(target=download_and_install, daemon=True).start()

    def check_thunderstore_title_exists(self, title):
        logging.debug(f"Checking if title '{title}' exists in Thunderstore mods")
        backend_title = self.get_backend_name(title)
        for mod in self.available_mods:
            logging.debug(f"Comparing with mod title: {mod['title']}")
            mod_backend_title = self.get_backend_name(mod['title'])
            if mod_backend_title.lower() == backend_title.lower():
                logging.debug(f"Found matching mod: {mod['title']}")
                return True
        logging.debug(f'No matching mod found for title: {title}')
        return False

    def import_zip_mod(self):
        try:
            zip_path = filedialog.askopenfilename(title='Select Mod Zip File', filetypes=[('ZIP files', '*.zip')])
            if not zip_path:
                logging.info('No ZIP file selected.')
                return
            logging.info(f'Selected ZIP file: {zip_path}')
            temp_dir = os.path.join(self.app_data_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            import_temp_dir = os.path.join(temp_dir, f'import_{int(time.time())}')
            os.makedirs(import_temp_dir)
            extracted_zip_dir = os.path.join(import_temp_dir, 'extractedzip')
            os.makedirs(extracted_zip_dir)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_zip_dir)
            manifest_path = self.find_manifest(extracted_zip_dir)
            if not manifest_path:
                error_msg = 'manifest.json not found in the ZIP file. This may not be a valid mod package.'
                logging.error(error_msg)
                messagebox.showerror('Error', error_msg)
                return
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            mod_id = manifest.get('Id')
            if not mod_id:
                error_msg = 'Id not found in manifest.json. This may not be a valid mod package.'
                logging.error(error_msg)
                messagebox.showerror('Error', error_msg)
                return
            mod_title = manifest.get('Metadata', {}).get('Name') or manifest.get('Name')
            if mod_title and self.check_thunderstore_title_exists(mod_title):
                if not messagebox.askokcancel('Thunderstore Mod Available', f"A mod named '{mod_title}' is available on Thunderstore. It's recommended to install from Thunderstore when possible for better compatibility and updates.\n\nWARNING: Installing a third-party version of a Thunderstore mod will likely cause bugs with the mod manager and updates.\n\nDo you still want to continue importing this third-party version?"):
                    return
            if (dependencies := manifest.get('Dependencies', [])):
                all_dependencies = []
                missing_dependencies = []
                for dep_id in dependencies:
                    if not self.is_mod_installed(dep_id):
                        if (dep_mod := self.find_mod_by_id(dep_id)):
                            if dep_mod not in all_dependencies:
                                all_dependencies.append(dep_mod)
                        else:
                            missing_dependencies.append(dep_id)
                if all_dependencies or missing_dependencies:
                    message = f"The mod '{manifest.get('Name', mod_id)}' has dependencies:\n\n"
                    if all_dependencies:
                        message += 'The following dependencies will be installed:\n'
                        message += '\n'.join([f"• {dep['title']}" for dep in all_dependencies])
                        message += '\n'
                    if missing_dependencies:
                        message += '\nThe following dependencies could not be found:\n'
                        message += '\n'.join([f'• {dep_id}' for dep in missing_dependencies])
                        message += '\n\nThe mod may not work correctly without these dependencies. Try finding and importing them manually.'
                    message += '\n\nWould you like to continue?'
                    if not messagebox.askyesno('Dependencies Required', message):
                        return
                    for dep_mod in all_dependencies:
                        self.set_status(f"Installing dependency: {dep_mod['title']}")
                        self.download_and_install_mod(dep_mod)
            if self.mod_id_exists(mod_id):
                messagebox.showwarning('Mod Conflict', f"A mod with ID '{mod_id}' already exists. You must uninstall the existing mod before importing a new mod with the same ID.")
                return
            mod_dir = os.path.join(self.mods_dir, '3rd_party', mod_id)
            if os.path.exists(mod_dir):
                shutil.rmtree(mod_dir)
            manifest_parent = os.path.dirname(manifest_path)
            if manifest_parent != extracted_zip_dir:
                shutil.move(manifest_parent, mod_dir)
            else:
                shutil.move(extracted_zip_dir, mod_dir)
            mod_info = {'id': mod_id, 'title': manifest.get('Metadata', {}).get('Name') or manifest.get('Name', mod_id), 'author': manifest.get('Metadata', {}).get('Author') or manifest.get('Author', 'Unknown'), 'description': manifest.get('Metadata', {}).get('Description') or manifest.get('Description', ''), 'version': manifest.get('Metadata', {}).get('Version') or manifest.get('Version', 'Unknown'), 'enabled': True, 'third_party': True, 'updated_on': int(time.time())}
            mod_info_path = os.path.join(mod_dir, 'mod_info.json')
            with open(mod_info_path, 'w') as f:
                json.dump(mod_info, f, indent=2)
            self.set_status(f"3rd party mod '{mod_info['title']}' imported successfully!")
            self.refresh_mod_lists()
            self.copy_mod_to_game(mod_info)
        except Exception as e:
            error_message = f'Failed to import mod: {str(e)}'
            logging.error(error_message)
            logging.error(traceback.format_exc())
            self.set_status(error_message)

    def find_manifest(self, directory):
        for root, dirs, files in os.walk(directory):
            if 'manifest.json' in files:
                manifest_path = os.path.join(root, 'manifest.json')
                try:
                    with open(manifest_path, 'r') as f:
                        manifest_data = json.load(f)
                        if manifest_data.get('Id'):
                            return manifest_path
                except (json.JSONDecodeError, IOError):
                    continue
        return None

    def refresh_all_mods(self):
        self.load_available_mods()
        self.refresh_mod_lists()
        self.set_status('All mods refreshed')

    def get_gdweave_version(self):

        def fetch_version():
            try:
                api_url = 'https://api.github.com/repos/NotNite/GDWeave/releases/latest'
                headers = {'Accept': 'application/vnd.github.v3+json'}
                response = requests.get(api_url, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                version = data['tag_name'].lstrip('v')
                logging.info(f'Successfully fetched GDWeave version: {version}')
                return version
            except requests.exceptions.RequestException as e:
                logging.error(f'Network error fetching GDWeave version: {str(e)}')
                return None
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                logging.error(f'Error parsing GDWeave version response: {str(e)}')
                return None
            except Exception as e:
                logging.error(f'Unexpected error fetching GDWeave version: {str(e)}')
                return None
        result = None

        def run_fetch():
            nonlocal result
            result = fetch_version()
        thread = threading.Thread(target=run_fetch, daemon=True)
        thread.start()
        thread.join(timeout=30)
        if thread.is_alive():
            logging.error('Timeout occurred while fetching GDWeave version')
            return 'Unknown'
        return result if result is not None else 'Unknown'

    def install_mod(self):
        logging.debug('Starting install_mod()')
        if not self.check_setup():
            logging.debug('Setup check failed')
            return
        selected = self.available_listbox.curselection()
        logging.debug(f'Selected items: {selected}')
        if not selected:
            logging.debug('No mods selected')
            self.set_status('Please select a mod to install')
            return
        selected_titles = [self.available_listbox.get(index) for index in selected]
        logging.debug(f'Selected titles: {selected_titles}')
        protected_mods = ['GDWeave', 'Buoy', 'r2modman', 'Hatchery']
        for title in selected_titles:
            clean_title = title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
            backend_title = self.get_backend_name(clean_title)
            logging.debug(f'Checking protected status for {backend_title}')
            if backend_title in protected_mods:
                logging.debug(f'{backend_title} is protected, showing error')
                messagebox.showerror('Protected Mod', f'{clean_title} cannot be installed via the Mod Manager tab.')
                return
        all_dependencies = []
        missing_dependencies = []
        try:
            for index in selected:
                mod_title = self.available_listbox.get(index)
                logging.debug(f'Processing mod: {mod_title}')
                if mod_title.startswith('Category:'):
                    logging.debug('Skipping category header')
                    continue
                clean_title = mod_title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
                backend_title = self.get_backend_name(clean_title)
                logging.debug(f'Cleaned title: {clean_title}, backend title: {backend_title}')
                mod = next((m for m in self.available_mods if self.get_backend_name(m['title'].strip()) == backend_title), None)
                if not mod:
                    logging.debug(f'Could not find mod for {backend_title}')
                    continue
                self.set_status_safe(f"Checking dependencies for {mod['title']}...")
                if (dependencies := mod.get('dependencies', [])):
                    logging.debug(f"Found dependencies for {mod['title']}: {dependencies}")
                    for dep in dependencies:
                        parts = dep.split('-')
                        if len(parts) >= 2:
                            thunderstore_id = f'{parts[0]}-{parts[1]}'
                            logging.debug(f'Checking dependency: {thunderstore_id}')
                            if thunderstore_id.startswith(('NotNet-GDWeave', 'PawsBeGamin-Buoy', 'ekbr-r2modman')):
                                logging.debug(f'Skipping core dependency: {thunderstore_id}')
                                continue
                            if not any((m.get('thunderstore_id') == thunderstore_id for m in self.installed_mods)):
                                logging.debug(f'Dependency {thunderstore_id} not installed')
                                if (dep_mod := next((m for m in self.available_mods if m.get('thunderstore_id') == thunderstore_id), None)):
                                    if dep_mod not in all_dependencies:
                                        logging.debug(f'Adding {thunderstore_id} to dependencies to install')
                                        all_dependencies.append(dep_mod)
                                else:
                                    logging.debug(f'Dependency {thunderstore_id} not found in available mods')
                                    missing_dependencies.append(dep)
            if all_dependencies or missing_dependencies:
                logging.debug(f'Found dependencies to handle - to install: {len(all_dependencies)}, missing: {len(missing_dependencies)}')
                message = ''
                if all_dependencies:
                    message += 'The following dependencies will be installed:\n'
                    for i, dep in enumerate(all_dependencies[:5]):
                        message += f"• {dep['title']}\n"
                    if len(all_dependencies) > 5:
                        message += f'...and {len(all_dependencies) - 5} more\n'
                    message += '\n'
                if missing_dependencies:
                    message += 'The following dependencies could not be found:\n'
                    for i, dep in enumerate(missing_dependencies[:5]):
                        message += f'• {dep}\n'
                    if len(missing_dependencies) > 5:
                        message += f'...and {len(missing_dependencies) - 5} more\n'
                    message += '\nThe mod may not work correctly without these dependencies.\n'
                message += 'Would you like to continue?'
                if not messagebox.askyesno('Dependencies Required', message):
                    logging.debug('User cancelled dependency installation')
                    return
                for dep_mod in all_dependencies:
                    logging.debug(f"Installing dependency: {dep_mod['title']}")
                    self.set_status_safe(f"Installing dependency: {dep_mod['title']}")
                    self.download_and_install_mod(dep_mod)
            for index in selected:
                mod_title = self.available_listbox.get(index)
                logging.debug(f'Installing selected mod: {mod_title}')
                if mod_title.startswith('Category:'):
                    logging.debug('Skipping category header')
                    continue
                clean_title = mod_title.replace('✅', '').replace('❌', '').replace('[3rd]', '').strip()
                backend_title = self.get_backend_name(clean_title)
                mod = next((m for m in self.available_mods if self.get_backend_name(m['title'].strip()) == backend_title), None)
                if not mod:
                    logging.debug(f'Could not find mod for {clean_title}')
                    continue
                self.set_status_safe(f"Installing {mod['title']}")
                logging.debug(f"Downloading and installing {mod['title']}")
                self.download_and_install_mod(mod)
            self.set_status_safe('Installation complete')
            logging.debug('Installation completed successfully')
            self.refresh_mod_lists()
        except Exception as e:
            error_message = f'Installation failed: {str(e)}'
            logging.debug(f'Installation failed with error: {error_message}')
            messagebox.showerror('Error', error_message)
            logging.ERROR(error_message)

    def is_mod_installed(self, mod_id):
        return any((m['id'] == mod_id for m in self.installed_mods))

    def find_mod_by_id(self, mod_id):
        return next((m for m in self.available_mods if m['id'] == mod_id), None)

    def check_mod_dependencies(self, mod):
        missing_deps = []
        for dep in mod.get('dependencies', []):
            parts = dep.split('-')
            if len(parts) >= 2:
                thunderstore_id = f'{parts[0]}-{parts[1]}'
                if thunderstore_id.startswith(('NotNet-GDWeave', 'PawsBeGamin-Buoy', 'ekbr-r2modman')):
                    continue
                if not any((m.get('thunderstore_id') == thunderstore_id for m in self.installed_mods)):
                    missing_deps.append(dep)
        return missing_deps

    def find_installed_mod_by_id(self, mod_id):
        for mod in self.installed_mods:
            if mod['id'] == mod_id:
                return mod
            third_party_dir = os.path.join(self.mods_dir, '3rd_party')
            if os.path.exists(third_party_dir):
                for mod_folder in os.listdir(third_party_dir):
                    mod_info_path = os.path.join(third_party_dir, mod_folder, 'mod_info.json')
                    if os.path.exists(mod_info_path):
                        with open(mod_info_path, 'r') as f:
                            mod_info = json.load(f)
                            if mod_info['id'] == mod_id:
                                return mod_info
            return None
        third_party_dir = os.path.join(self.mods_dir, '3rd_party')
        if os.path.exists(third_party_dir):
            for mod_folder in os.listdir(third_party_dir):
                mod_info_path = os.path.join(third_party_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        if mod_info['id'] == mod_id:
                            return mod_info
        return None

    def install_gdweave(self):
        if not self.settings.get('game_path'):
            self.set_status('Please set the game path first')
            return
        gdweave_url = 'https://github.com/NotNite/GDWeave/releases/latest/download/GDWeave.zip'
        game_path = self.settings['game_path']
        gdweave_path = os.path.join(game_path, 'GDWeave')
        try:
            temp_dir = os.path.join(os.getenv('APPDATA'), 'Hook_Line_Sinker_Reborn', 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_backup_dir = os.path.join(temp_dir, f'gdweave_backup_{int(time.time())}')
            os.makedirs(temp_backup_dir, exist_ok=True)
            mods_path = os.path.join(gdweave_path, 'Mods')
            configs_path = os.path.join(gdweave_path, 'configs')
            if os.path.exists(mods_path):
                shutil.copytree(mods_path, os.path.join(temp_backup_dir, 'Mods'))
                logging.info('Backed up Mods folder')
            if os.path.exists(configs_path):
                shutil.copytree(configs_path, os.path.join(temp_backup_dir, 'configs'))
                logging.info('Backed up configs folder')
            self.set_status('Downloading GDWeave...')
            response = requests.get(gdweave_url)
            response.raise_for_status()
            zip_path = os.path.join(temp_dir, 'GDWeave.zip')
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            self.set_status('Installing GDWeave...')
            logging.info(f'Zip file downloaded to: {zip_path}')
            extract_path = os.path.join(temp_dir, 'GDWeave_extract')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            logging.info(f'Zip file extracted to: {extract_path}')
            if os.path.exists(gdweave_path):
                logging.info(f'Removing existing GDWeave folder: {gdweave_path}')
                shutil.rmtree(gdweave_path)
            extracted_gdweave_path = os.path.join(extract_path, 'GDWeave')
            logging.info(f'Moving {extracted_gdweave_path} to {gdweave_path}')
            shutil.move(extracted_gdweave_path, gdweave_path)
            if sys.platform.startswith('win'):
                winmm_src = os.path.join(extract_path, 'winmm.dll')
                winmm_dst = os.path.join(game_path, 'winmm.dll')
                logging.info(f'Copying {winmm_src} to {winmm_dst}')
                shutil.copy2(winmm_src, winmm_dst)
            if os.path.exists(os.path.join(temp_backup_dir, 'Mods')):
                shutil.copytree(os.path.join(temp_backup_dir, 'Mods'), os.path.join(gdweave_path, 'Mods'), dirs_exist_ok=True)
                logging.info('Restored Mods folder')
            if os.path.exists(os.path.join(temp_backup_dir, 'configs')):
                shutil.copytree(os.path.join(temp_backup_dir, 'configs'), os.path.join(gdweave_path, 'configs'), dirs_exist_ok=True)
                logging.info('Restored configs folder')
            self.settings['gdweave_version'] = self.get_gdweave_version()
            self.save_settings()
            self.set_status(f"GDWeave {self.settings['gdweave_version']} installed/updated successfully")
            self.update_setup_status()
            logging.info('GDWeave installed/updated successfully!')
        except requests.exceptions.RequestException as e:
            error_message = f'Failed to download GDWeave: {str(e)}'
            self.set_status(error_message)
            logging.info(error_message)
            logging.info(f'Error details: {traceback.format_exc()}')
        except Exception as e:
            error_message = f'Failed to install/update GDWeave: {str(e)}'
            self.set_status(error_message)
            logging.info(error_message)
            logging.info(f'Error details: {traceback.format_exc()}')
        self.refresh_mod_lists()

    def update_setup_status(self):
        self.update_step1_status()
        self.update_step2_status()
        self.update_step4_status()
        if self.is_gdweave_installed():
            self.gdweave_button.config(text='Update GDWeave')
            self.gdweave_label.config(text='Updates GDWeave mod loader to the latest version and preserves your mods')
        else:
            self.gdweave_button.config(text='Install GDWeave')
            self.gdweave_label.config(text='Installs GDWeave mod loader which is required for mod functionality')

    def is_gdweave_enabled(self):
        if not self.settings.get('game_path'):
            return False
        game_path = self.settings['game_path']
        gdweave_game_path = os.path.join(game_path, 'GDWeave')
        if sys.platform.startswith('win'):
            return os.path.exists(gdweave_game_path) or os.path.exists(os.path.join(game_path, 'winmm.dll'))
        return False

    def update_step1_status(self):
        if self.settings.get('game_path') and os.path.exists(self.settings['game_path']):
            self.step1_status.config(text='Verified', foreground='green')
        else:
            self.step1_status.config(text='Unverified', foreground='red')

    def update_step2_status(self):
        if self.settings.get('game_path'):
            exe_path = os.path.join(self.settings['game_path'], 'webfishing.exe' if sys.platform.startswith('win') else 'webfishing.x86_64')
            if os.path.isfile(exe_path):
                self.step2_status.config(text='Verified', foreground='green')
            else:
                self.step2_status.config(text='Unverified', foreground='red')
        else:
            self.step2_status.config(text='Unverified', foreground='red')

    def update_step4_status(self):
        try:
            if self.is_gdweave_installed():
                current_version = self.settings.get('gdweave_version', 'Unknown')
                latest_version = self.get_gdweave_version()
                if current_version == latest_version:
                    self.step4_status.config(text='Up to Date', foreground='green')
                else:
                    self.step4_status.config(text='Out of Date', foreground='orange')
            else:
                backup_path = os.path.join(self.app_data_dir, 'GDWeave_Backup')
                if os.path.exists(backup_path):
                    self.step4_status.config(text='Disabled (Backup Available)', foreground='orange')
                else:
                    self.step4_status.config(text='Uninstalled', foreground='red')
        except Exception as e:
            self.step4_status.config(text=f'Error: {str(e)}', foreground='red')

    def is_setup_complete(self):
        return self.settings.get('game_path') and os.path.exists(self.settings['game_path']) and self.check_dotnet(silent=True) and (self.is_gdweave_installed() or self.settings.get('gdweave_version'))

    def is_gdweave_installed(self):
        if not self.settings.get('game_path'):
            return False
        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        return os.path.exists(gdweave_path)

    def check_dotnet(self, silent=False):
        try:
            subprocess.run(['dotnet', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not silent:
                self.set_status('.NET is installed')
            return True
        except Exception as e:
            if not silent:
                self.set_status(f'Error: {str(e)}. .NET is not installed. Please install .NET 8.0 SDK from https://dotnet.microsoft.com/download')
            return False

    def open_dotnet_download(self):
        webbrowser.open('https://dotnet.microsoft.com/download')

    def create_help_tab(self):
        help_frame = ttk.Frame(self.notebook)
        self.notebook.add(help_frame, text='Troubleshooting')
        help_frame.grid_columnconfigure(0, weight=1)
        help_frame.grid_rowconfigure(2, weight=1)
        title_label = ttk.Label(help_frame, text='Troubleshooting Guide', font=('Helvetica', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(20, 5), padx=20, sticky='w')
        subtitle_label = ttk.Label(help_frame, text="If you're experiencing any problems, please try all these steps first", font=('Helvetica', 10, 'italic'))
        subtitle_label.grid(row=1, column=0, pady=(0, 10), padx=20, sticky='w')
        canvas = tk.Canvas(help_frame)
        scrollbar = ttk.Scrollbar(help_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=2, column=0, sticky='nsew', padx=20, pady=10)
        scrollbar.grid(row=2, column=1, sticky='ns')

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        help_frame.grid_rowconfigure(2, weight=1)
        help_items = [('1. Install .NET 8.0 SDK Manually', "If you're having issues with .NET:\n- Visit the .NET Download Page\n- Download and install the .NET 8.0 SDK", 'https://dotnet.microsoft.com/download'), ('2. Install GDWeave Manually', 'If automatic GDWeave installation fails:\n- Go to GDWeave Releases\n- Download the latest GDWeave.zip\n- Extract it to your WEBFISHING game directory', 'https://github.com/NotNite/GDWeave/releases'), ('3. Installing External Mods', "For mods not listed in our repository:\n- Use the 'Import ZIP Mod' feature in the Mod Manager tab\n- Select the .zip file of the mod you want to install\n- The mod will be automatically imported and installed", None), ('4. Run as Administrator (Windows)', "If you're having permission issues on Windows:\n- Right-click on Buoy executable\n- Select 'Run as administrator'", None), ('5. Verify Game Files', "If mods aren't working:\n- Verify your game files through Steam\n- Reinstall GDWeave", None), ('6. Check Antivirus Software', 'Your antivirus might be blocking Buoy or mods:\n- Add an exception for the Buoy directory\n- Add an exception for your WEBFISHING game directory', None), ('7. Linux-Specific Issues', "If you're on Linux and having problems:\n- Ensure you have the necessary dependencies installed (e.g., mono-complete)\n- Check if you need to run the game with a specific command or script\n- Make sure you have the required permissions to access game files", None)]
        for i, (title, content, link) in enumerate(help_items):
            item_frame = ttk.Frame(scrollable_frame)
            item_frame.grid(row=i, column=0, sticky='ew', padx=10, pady=5)
            item_frame.grid_columnconfigure(0, weight=1)
            ttk.Label(item_frame, text=title, font=('Helvetica', 12, 'bold')).grid(row=0, column=0, sticky='w', pady=(5, 2))
            ttk.Label(item_frame, text=content, wraplength=500, justify='left').grid(row=1, column=0, sticky='w', padx=20)
            if link:
                ttk.Button(item_frame, text='Open Link', command=lambda url=link: webbrowser.open(url)).grid(row=2, column=0, sticky='w', padx=20, pady=(5, 0))
        more_help_frame = ttk.Frame(scrollable_frame)
        more_help_frame.grid(row=len(help_items), column=0, sticky='ew', padx=10, pady=20)
        more_help_frame.grid_columnconfigure(0, weight=1)
        contact_info = "If you're still having issues, please contact me:\n- Discord: @pawbies"
        ttk.Label(more_help_frame, text=contact_info, wraplength=500, justify='left').grid(row=2, column=0, sticky='w', padx=20, pady=(10, 0))

    def make_links_clickable(self, label):
        text = label.cget('text')
        links = re.findall('\\[([^\\]]+)\\]\\(([^\\)]+)\\)', text)
        for link_text, url in links:
            text = text.replace(f'[{link_text}]({url})', link_text)
        label.config(text=text)

        def open_link(event):
            for link_text, url in links:
                if link_text in event.widget.cget('text'):
                    webbrowser.open(url)
                    break
        label.bind('<Button-1>', open_link)
        label.config(cursor='hand2', foreground='blue')

    def open_buoy_folder(self):
        if sys.platform.startswith('win'):
            os.startfile(self.app_data_dir)
        elif sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', self.app_data_dir])
        else:
            messagebox.showerror('Error', 'Unsupported operating system')

    def open_gdweave_folder(self):
        gdweave_path = os.path.join(self.settings['game_path'], 'GDWeave')
        if os.path.exists(gdweave_path):
            if sys.platform.startswith('win'):
                os.startfile(gdweave_path)
            else:
                messagebox.showerror('Error', 'Unsupported operating system')
        else:
            messagebox.showerror('Error', 'GDWeave folder not found. Make sure GDWeave is installed.')

    def open_gdweave_log(self):
        log_path = os.path.join(self.settings['game_path'], 'GDWeave', 'GDWeave.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_content = f.read()
            log_window = tk.Toplevel(self.root)
            log_window.title('GDWeave Log')
            log_window.geometry('800x600')
            log_window.configure(background=self.dark_mode_colors['bg'])
            icon_path = get_resource_path('images/icon.ico')
            if os.path.exists(icon_path):
                log_window.iconbitmap(icon_path)
            log_text = tk.Text(log_window, wrap=tk.NONE, font=('Consolas', 10), bg=self.dark_mode_colors['bg'], fg=self.dark_mode_colors['fg'])
            log_text.pack(expand=True, fill='both')
            log_text.insert(tk.END, log_content)
            log_text.config(state='disabled')
            scrollbar = ttk.Scrollbar(log_text)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            log_text.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=log_text.yview)
            copy_button = ttk.Button(log_window, text='Copy to Clipboard', command=lambda: self.copy_to_clipboard(log_content))
            copy_button.pack(pady=10)
        else:
            messagebox.showerror('Error', 'GDWeave log file not found. Make sure GDWeave is installed and has been run at least once.')

    def copy_to_clipboard(self, content):
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo('Success', 'Log content copied to clipboard!')

    def clear_gdweave_mods(self):
        if not messagebox.askyesno('Confirm Clear', "Are you sure you want to remove all mods from the game's mods folder? This action cannot be undone."):
            return
        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        if os.path.exists(gdweave_mods_path):
            try:
                for item in os.listdir(gdweave_mods_path):
                    item_path = os.path.join(gdweave_mods_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                self.set_status("All mods have been removed from the game's mods folder.")
            except Exception as e:
                self.set_status(f'Error clearing GDWeave mods: {str(e)}')
        else:
            self.set_status('GDWeave mods folder not found.')

    def clear_buoy_mods(self):
        if not messagebox.askyesno('Confirm Clear', 'Are you sure you want to remove all mods managed by Buoy? This action cannot be undone.'):
            return
        try:
            for item in os.listdir(self.mods_dir):
                item_path = os.path.join(self.mods_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            self.mod_cache = {}
            self.save_mod_cache()
            self.refresh_mod_lists()
            self.set_status('All Buoy managed mods and cache have been cleared.')
        except Exception as e:
            self.set_status(f'Error clearing Buoy mods: {str(e)}')

    def process_gui_queue(self):
        try:
            while True:
                message = self.gui_queue.get_nowait()
                if message[0] == 'latest_version':
                    self.latest_version_label.config(text=f'Latest Version: {message[1]}')
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_gui_queue)

    def find_mod_by_title(self, title):
        if title.startswith('✅ ') or title.startswith('❌ '):
            title = title[2:].strip()
        if '[3rd]' in title:
            title = title.replace('[3rd]', '').strip()
        for mod in self.installed_mods:
            if mod['title'] == title:
                return mod
        for mod in self.available_mods:
            if mod['title'] == title:
                return mod
        raise ValueError(f'no mod found with title: {title}')

    def update_available_mods_list(self):
        self.available_listbox.delete(0, tk.END)
        for mod in sorted(self.available_mods, key=lambda x: x['title']):
            display_title = self.get_display_name(mod['title'])
            self.available_listbox.insert(tk.END, display_title)

    def extract_mod_from_zip(self, zip_path, temp_dir):
        """Extract mod from zip file by finding manifest.json with Id field"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            manifest_files = []
            for root, _, files in os.walk(temp_dir):
                if 'manifest.json' in files:
                    manifest_path = os.path.join(root, 'manifest.json')
                    try:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            if 'Id' in manifest:
                                mod_id = manifest['Id']
                                manifest_files.append((manifest_path, mod_id))
                    except (json.JSONDecodeError, KeyError):
                        continue
            if not manifest_files:
                raise ValueError('No valid manifest.json with Id field found in mod package')
            manifest_path, mod_id = manifest_files[0]
            mod_dir = os.path.dirname(manifest_path)
            if not os.path.exists(mod_dir):
                raise ValueError('Mod directory not found after extraction')
            return mod_dir
        except Exception as e:
            raise ValueError(f'Failed to extract mod: {str(e)}')

    def create_status_bar(self):
        self.status_bar = ttk.Label(self.root, text='Ready', relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, message):
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def edit_mod_config(self):
        selected_indices = self.get_selected_installed_mod_indices()
        if not selected_indices:
            messagebox.showinfo('No Mod Selected', 'Please select a mod to edit its configuration.')
            return
        if not self.settings.get('game_path'):
            messagebox.showerror('Error', 'Game path not set. Please set the game path in the settings.')
            return
        mod = self.filtered_installed_mods[selected_indices[0]]
        config_path = os.path.join(self.settings['game_path'], 'GDWeave', 'configs', f"{mod['id']}.json")
        if not os.path.exists(config_path):
            messagebox.showinfo('No Config Found', f"{mod['title']} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
            return
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            if not config:
                messagebox.showinfo('No Config Found', f"{mod['title']} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
                return
            self.open_config_editor(mod['title'], config, config_path)
        except json.JSONDecodeError:
            messagebox.showerror('Error', f"Failed to parse the configuration file for {mod['title']}.")
        except Exception as e:
            messagebox.showerror('Error', f'An error occurred while trying to edit the configuration: {str(e)}')

    def open_config_editor(self, mod_name, config, config_path):
        if not config:
            messagebox.showinfo('No Config Found', f"{mod_name} doesn't have a config. Either this mod doesn't require one, or you need to restart your game to generate the config.")
            return
        editor_window = tk.Toplevel(self.root)
        editor_window.title(f'Edit Config: {mod_name}')
        editor_window.geometry('600x600')
        icon_path = get_resource_path('images/icon.ico')
        if os.path.exists(icon_path):
            editor_window.iconbitmap(icon_path)
        editor_window.configure(bg='#2b2b2b')
        style = ttk.Style()
        style.configure('MainFrame.TFrame', background='#2b2b2b')
        style.configure('HeaderFrame.TFrame', background='#2b2b2b')
        style.configure('ContentFrame.TFrame', background='#2b2b2b')
        style.configure('ScrollableFrame.TFrame', background='#2b2b2b')
        style.configure('Vertical.TScrollbar', background='#2b2b2b', troughcolor='#3c3c3c', arrowcolor='#FFFFFF')
        style.configure('HeaderLabel.TLabel', background='#2b2b2b', foreground='#FFFFFF', font=('TkDefaultFont', 10, 'bold'))
        main_frame = ttk.Frame(editor_window, padding='10', style='MainFrame.TFrame')
        main_frame.pack(fill='both', expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        header_frame = ttk.Frame(main_frame, style='HeaderFrame.TFrame')
        header_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)
        ttk.Label(header_frame, text=f'Editing configuration for {mod_name}', font=('TkDefaultFont', 10, 'bold'), style='HeaderLabel.TLabel').pack(side='left', fill='x', expand=True)
        content_frame = ttk.Frame(main_frame, style='ContentFrame.TFrame')
        content_frame.grid(row=1, column=0, sticky='nsew')
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)
        canvas = tk.Canvas(content_frame, bg='#2b2b2b', highlightbackground='#FFFFFF', highlightthickness=1)
        scrollbar = ttk.Scrollbar(content_frame, orient='vertical', command=canvas.yview, style='Vertical.TScrollbar')
        scrollable_frame = ttk.Frame(canvas, style='ScrollableFrame.TFrame')
        scrollable_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        content_frame.rowconfigure(0, weight=1)

        def resize_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width - scrollbar.winfo_width())
        canvas.bind('<Configure>', resize_canvas)
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', on_mousewheel)
        config_vars = {}
        for i, (key, value) in enumerate(config.items()):
            display_name = key
            if key in ['FishIDs', 'ID', 'IDs', 'XP'] or ('_' not in key and (not any((c.isupper() for c in key[1:])))):
                display_name = key
            else:
                display_name = ''.join([' ' + c if c.isupper() else c for c in display_name]).strip()
                display_name = display_name.replace('_', ' ')
                display_name = ' '.join((word.capitalize() for word in display_name.split()))
            item_frame = ttk.LabelFrame(scrollable_frame, text=display_name, padding='5')
            item_frame.pack(fill='x', pady=5)
            item_frame.columnconfigure(0, weight=1)
            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                ttk.Checkbutton(item_frame, variable=var, text='Enabled').pack(anchor='w')
            elif isinstance(value, (int, float)):
                var = tk.StringVar(value=str(value))
                ttk.Entry(item_frame, textvariable=var).pack(fill='x')
            elif isinstance(value, list):
                var = tk.StringVar(value=', '.join(map(str, value)))
                entry_frame = ttk.Frame(item_frame)
                entry_frame.pack(fill='x')
                entry_frame.columnconfigure(0, weight=1)
                ttk.Entry(entry_frame, textvariable=var).pack(side='left', fill='x', expand=True)
                ttk.Label(entry_frame, text='(comma-separated values)').pack(side='right', padx=(5, 0))
            elif isinstance(value, dict):
                text_widget = tk.Text(item_frame, height=4, wrap='word', background='#3c3c3c', foreground='#FFFFFF', relief='flat')
                text_widget.insert('1.0', json.dumps(value, indent=2))
                text_widget.pack(fill='both', expand=True)
                var = text_widget
            else:
                var = tk.StringVar(value=str(value))
                ttk.Entry(item_frame, textvariable=var).pack(fill='x')
            config_vars[key] = (var, type(value))
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        button_frame.columnconfigure(0, weight=1)
        def save_config():
            try:
                new_config = {}
                for k, (var, value_type) in config_vars.items():
                    if value_type == bool:
                        new_config[k] = var.get()
                    elif value_type in (int, float):
                        try:
                            new_config[k] = value_type(var.get())
                        except ValueError:
                            raise ValueError(f"Invalid {value_type.__name__} value for {k}")
                    elif value_type == list:
                        try:
                            values = [v.strip() for v in var.get().split(",")]
                            new_config[k] = [v for v in values if v]
                        except Exception:
                            raise ValueError(f"Invalid array value for {k}")
                    elif value_type == dict:
                        try:
                            new_config[k] = json.loads(var.get("1.0", tk.END))
                        except json.JSONDecodeError:
                            raise ValueError(f"Invalid JSON object for {k}")
                    else:
                        new_config[k] = var.get()

                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=2)
                messagebox.showinfo("Success", f"Configuration for {mod_name} has been updated.")
                editor_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

        def restore_defaults():
            if messagebox.askyesno("Restore Defaults", 
                                 "Are you sure you want to restore defaults? This is irreversible!"):
                try:
                    os.remove(config_path)
                    messagebox.showinfo("Success", 
                                      "Configuration has been reset. Please restart your game for the defaults to take effect.")
                    editor_window.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to restore defaults: {str(e)}")

        ttk.Button(button_frame, text="Save", command=save_config, style='Accent.TButton').pack(side="left", padx=5)
        ttk.Button(button_frame, text="Restore Defaults", command=restore_defaults).pack(side="left")
        ttk.Button(button_frame, text="Cancel", command=editor_window.destroy).pack(side="right", padx=5)


    def show_context_menu(self, event):
        listbox = event.widget
        index = listbox.nearest(event.y)
        menu = tk.Menu(self.root, tearoff=0)
        if index != -1:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(index)
            listbox.activate(index)
            if listbox == self.available_listbox:
                selected_title = listbox.get(index)
                mod = next((m for m in self.available_mods if self.get_display_name(m['title']) == selected_title), None)
                if mod:
                    menu.add_command(label='Install', command=self.install_mod)
            elif listbox == self.installed_listbox:
                selected_text = listbox.get(index)
                clean_title = re.sub('^[✅❌]\\s*(?:\\[3rd\\]\\s*)?', '', selected_text)
                mod = next((m for m in self.installed_mods if self.get_display_name(m['title']) == clean_title), None)
                if mod:
                    if self.mod_has_config(mod):
                        menu.add_command(label='Edit Config', command=self.edit_mod_config)
                    menu.add_command(label='Test Mod', command=lambda: self.test_mod(mod))
                    menu.add_separator()
                    version_menu = tk.Menu(menu, tearoff=0)
                    menu.add_cascade(label='Version Management', menu=version_menu)
                    version_menu.add_command(label='Mark Current Version as Unwanted', command=lambda: self.blacklist_version(mod))
                    version_menu.add_command(label='View Blacklisted Versions', command=lambda: self.show_blacklisted_versions(mod))
                    menu.add_separator()
                    menu.add_command(label='Enable', command=self.enable_mod)
                    menu.add_command(label='Disable', command=self.disable_mod)
                    menu.add_command(label='Uninstall', command=self.uninstall_mod)
                    if mod.get('enabled', True):
                        menu.add_separator()
                        menu.add_command(label='Open Folder', command=lambda: self.open_mod_folder(mod))
                    if mod.get('third_party', False):
                        menu.add_separator()
                        menu.add_command(label='Export as ZIP', command=lambda: self.export_mod_as_zip(mod))
            menu.tk_popup(event.x_root, event.y_root)

    def open_mod_folder(self, mod):
        if not self.settings.get('game_path'):
            messagebox.showerror('Error', 'Game path not set')
            return
        mod_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod['id'])
        if not os.path.exists(mod_path):
            messagebox.showerror('Error', 'Mod folder not found. Make sure the mod is enabled and installed.')
            return
        if sys.platform.startswith('win'):
            os.startfile(mod_path)
        elif sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', mod_path])
        else:
            messagebox.showerror('Error', 'Unsupported operating system')

    def mod_has_config(self, mod):
        if not self.settings.get('game_path'):
            return False
        config_path = os.path.join(self.settings['game_path'], 'GDWeave', 'configs', f"{mod['id']}.json")
        return os.path.exists(config_path)

    def get_mod_versions(self, mod):
        try:
            if not mod.get('thunderstore_id'):
                return []
            response = requests.get('https://thunderstore.io/c/webfishing/api/v1/package/')
            response.raise_for_status()
            all_mods = response.json()
            mod_data = next((m for m in all_mods if f"{m['owner']}-{m['name']}" == mod['thunderstore_id']), None)
            if not mod_data:
                return []
            versions = sorted(mod_data['versions'], key=lambda x: x['date_created'], reverse=True)[:20]
            return versions
        except Exception as e:
            logging.error(f"Error fetching versions for {mod['title']}: {str(e)}")
            return []

    def install_specific_version(self, mod, version):
        try:
            temp_mod = mod.copy()
            temp_mod.update({'version': version['version_number'], 'download': version['download_url'], 'dependencies': version['dependencies']})
            if messagebox.askyesno('Install Specific Version', f"Are you sure you want to install v{version['version_number']} of {mod['title']}?\n\nThis will replace the current version."):
                self.download_and_install_mod(temp_mod)
        except Exception as e:
            error_message = f"Failed to install version {version['version_number']}: {str(e)}"
            self.set_status(error_message)
            messagebox.showerror('Error', error_message)

    def test_mod(self, mod):
        try:
            dependencies = self.check_mod_dependencies(mod)
            for installed_mod in self.installed_mods:
                if installed_mod.get('enabled', True):
                    installed_mod['enabled'] = False
                    self.update_mod_status_in_listbox(installed_mod)
                    self.save_mod_status(installed_mod)
                    self.remove_mod_from_game(installed_mod)
            mods_to_enable = [mod]
            if dependencies:
                for dep_id in dependencies:
                    if (dep_mod := next((m for m in self.installed_mods if m['id'] == dep_id), None)):
                        mods_to_enable.append(dep_mod)
            for mod_to_enable in mods_to_enable:
                mod_to_enable['enabled'] = True
                self.update_mod_status_in_listbox(mod_to_enable)
                self.save_mod_status(mod_to_enable)
                self.copy_mod_to_game(mod_to_enable)
            self.refresh_mod_lists()
            if len(mods_to_enable) > 1:
                dep_names = ', '.join((m['title'] for m in mods_to_enable[1:]))
                self.set_status(f"Test mode enabled for {mod['title']} with dependencies: {dep_names}")
                messagebox.showinfo('Test Mode', f"Mod test mode enabled for {mod['title']} and its dependencies: {dep_names}")
            else:
                self.set_status(f"Test mode enabled for: {mod['title']}")
                messagebox.showinfo('Test Mode', 'Mod test mode enabled. All other mods have been disabled.')
        except Exception as e:
            error_message = f'Failed to enable test mode: {str(e)}'
            self.set_status(error_message)
            messagebox.showerror('Error', error_message)

    def blacklist_version(self, mod):
        version = mod.get('version', 'Unknown')
        mod_id = mod.get('thunderstore_id')
        if not mod_id:
            error_msg = 'Cannot blacklist version for this mod type'
            messagebox.showerror('Error', error_msg)
            return
        if messagebox.askyesno('Confirm Blacklist', f"Are you sure you want to mark version {version} of {mod['title']} as unwanted?\n\nThis version will be skipped during auto-updates."):
            if 'blacklisted_versions' not in self.settings:
                self.settings['blacklisted_versions'] = {}
            if mod_id not in self.settings['blacklisted_versions']:
                self.settings['blacklisted_versions'][mod_id] = []
            if version not in self.settings['blacklisted_versions'][mod_id]:
                self.settings['blacklisted_versions'][mod_id].append(version)
                self.save_settings()
                messagebox.showinfo('Success', f'Version {version} has been marked as unwanted')

    def show_blacklisted_versions(self, mod):
        mod_id = mod.get('thunderstore_id')
        if not mod_id or not self.settings.get('blacklisted_versions', {}).get(mod_id):
            messagebox.showinfo('No Blacklisted Versions', 'No versions have been marked as unwanted for this mod')
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Blacklisted Versions - {mod['title']}")
        dialog.geometry('300x400')
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text='The following versions will be skipped:').pack(pady=10)
        listbox = tk.Listbox(dialog)
        listbox.pack(fill='both', expand=True, padx=10, pady=5)
        for version in self.settings['blacklisted_versions'][mod_id]:
            listbox.insert(tk.END, version)

        def remove_selected():
            selection = listbox.curselection()
            if selection:
                version = listbox.get(selection[0])
                if messagebox.askyesno('Confirm Remove', f'Remove version {version} from blacklist?'):
                    self.settings['blacklisted_versions'][mod_id].remove(version)
                    self.save_settings()
                    listbox.delete(selection[0])
        ttk.Button(dialog, text='Remove Selected', command=remove_selected).pack(pady=10)
        ttk.Button(dialog, text='Close', command=dialog.destroy).pack(pady=5)

    def export_mod_as_zip(self, mod):
        try:
            mod_dir = os.path.join(self.mods_dir, '3rd_party', mod['id'])
            if not os.path.exists(mod_dir):
                messagebox.showerror('Error', 'Mod directory not found.')
                return
            zip_path = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('ZIP files', '*.zip')], initialfile=f"{mod['title']}.zip")
            if not zip_path:
                return
            self.set_status(f"Exporting {mod['title']} as ZIP...")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(mod_dir):
                    for file in files:
                        if file != 'mod_info.json':
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, mod_dir)
                            zipf.write(file_path, arcname)
            self.set_status(f"Successfully exported {mod['title']} to {zip_path}")
            messagebox.showinfo('Success', f'Mod exported successfully to:\n{zip_path}')
        except Exception as e:
            error_message = f'Failed to export mod: {str(e)}'
            self.set_status(error_message)
            messagebox.showerror('Error', error_message)

    def enable_mod(self):
        if not self.check_setup():
            return
        if (selected := self.installed_listbox.curselection()):
            try:
                for index in selected:
                    mod = self.filtered_installed_mods[index]
                    mod['enabled'] = True
                    self.update_mod_status_in_listbox(mod)
                    self.save_mod_status(mod)
                    self.copy_mod_to_game(mod)
                    logging.info(f"Enabled mod: {mod['title']} (ID: {mod['id']}, Third Party: {mod.get('third_party', False)})")
                self.refresh_mod_lists()
                self.set_status(f'Enabled {len(selected)} mod(s)')
            except Exception as e:
                error_msg = f'Failed to enable mod: {str(e)}'
                logging.error(error_msg)
                self.set_status(error_msg)

    def copy_third_party_mod_to_game(self, mod):
        src_path = os.path.join(self.mods_dir, '3rd_party', mod['id'])
        dst_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod['id'])
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        self.set_status(f"Installed 3rd party mod: {mod['title']}")
        self.refresh_mod_lists()

    def uninstall_mod(self):
        selected_indices = self.get_selected_installed_mod_indices()
        if selected_indices:
            for index in selected_indices:
                mod = self.filtered_installed_mods[index]
                self.set_status(f"Uninstalling mod: {mod['title']}")
                try:
                    self.uninstall_mod_files(mod)
                except Exception as e:
                    error_message = f"Failed to uninstall mod {mod['title']}: {str(e)}"
                    self.set_status(error_message)
            self.refresh_mod_lists()

    def uninstall_mod_files(self, mod):
        if mod.get('third_party', False):
            mod_path = os.path.join(self.mods_dir, '3rd_party', mod['id'])
        else:
            mod_path = os.path.join(self.mods_dir, mod['id'])
        if os.path.exists(mod_path):
            shutil.rmtree(mod_path)
        game_mod_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod['id'])
        if os.path.exists(game_mod_path):
            shutil.rmtree(game_mod_path)
        self.set_status(f"Uninstalled mod: {mod['title']}")

    def enable_mod(self):
        if not self.check_setup():
            return
        selected_indices = self.get_selected_installed_mod_indices()
        if selected_indices:
            enabled_count = 0
            for index in selected_indices:
                mod = self.filtered_installed_mods[index]
                if not mod.get('enabled', True):
                    mod['enabled'] = True
                    self.update_mod_status_in_listbox(mod)
                    self.save_mod_status(mod)
                    self.copy_mod_to_game(mod)
                    enabled_count += 1
                    logging.info(f"Enabled mod: {mod['title']} (ID: {mod['id']}, Third Party: {mod.get('third_party', False)})")
            if enabled_count > 0:
                self.refresh_mod_lists()
                self.set_status(f'Enabled {enabled_count} mod(s)')
            else:
                self.set_status('No mods were enabled. Selected mods may already be enabled.')

    def disable_mod(self):
        if not self.check_setup():
            return
        selected_indices = self.get_selected_installed_mod_indices()
        if selected_indices:
            disabled_count = 0
            for index in selected_indices:
                mod = self.filtered_installed_mods[index]
                try:
                    mod['enabled'] = False
                    self.update_mod_status_in_listbox(mod)
                    self.save_mod_status(mod)
                    self.remove_mod_from_game(mod)
                    disabled_count += 1
                except Exception as e:
                    error_message = f"Failed to disable mod {mod.get('title')}: {str(e)}"
                    logging.error(error_message)
            self.refresh_mod_lists()
            self.set_status(f'Disabled {disabled_count} mod(s)')

    def create_mod_json(self, mod_folder, mod_name):
        mod_info = {'title': mod_name, 'author': 'Unknown', 'description': 'Imported mod', 'enabled': True, 'version': 'Unknown'}
        with open(os.path.join(mod_folder, 'mod.json'), 'w') as f:
            json.dump(mod_info, f)

    def check_setup(self):
        if not self.settings.get('game_path') or not os.path.exists(self.settings.get('game_path')):
            messagebox.showinfo('Setup Required', 'Please follow all the steps for installation in the Buoy Setup tab.')
            return False
        return True

    def update_mod_status_in_listbox(self, mod):
        index = self.installed_mods.index(mod)
        status = '✅' if mod.get('enabled', True) else '❌'
        third_party = '[3rd] ' if mod.get('third_party', False) else ''
        self.installed_listbox.delete(index)
        self.installed_listbox.insert(index, f"{status} {third_party}{mod['title']}".strip())

    def show_version_selection(self):
        selected_indices = self.get_selected_installed_mod_indices()
        if not selected_indices:
            messagebox.showerror('Error', 'Please select a mod to change version')
            return
        selected_mod = self.filtered_installed_mods[selected_indices[0]]
        versions = self.get_mod_versions(selected_mod)
        if not versions:
            messagebox.showerror('Error', 'No other versions available for this mod')
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Select Version')
        dialog.geometry('300x400')
        dialog.configure(bg=self.dark_mode_colors['bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        icon_path = get_resource_path('images/icon.ico')
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = dialog.winfo_screenwidth() // 2 - width // 2
        y = dialog.winfo_screenheight() // 2 - height // 2
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        ttk.Label(dialog, text='Select version to install:', background=self.dark_mode_colors['bg'], foreground='white').pack(pady=10, padx=10)
        version_listbox = tk.Listbox(dialog, width=40, height=15, relief=tk.FLAT, bg=self.dark_mode_colors['bg'], fg='white', selectbackground='white', selectforeground='black')
        version_listbox.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        current_version = selected_mod.get('version', 'Unknown')
        for version in versions:
            version_number = version['version_number']
            display_text = f"{selected_mod['title']} (v{version_number})"
            if version_number == current_version:
                display_text += ' (Current)'
            version_listbox.insert(tk.END, display_text)
        last_hovered_index = [-1]

        def on_listbox_hover(event):
            widget = event.widget
            current_index = widget.nearest(event.y)
            if last_hovered_index[0] != current_index:
                if 0 <= last_hovered_index[0] < widget.size():
                    widget.itemconfig(last_hovered_index[0], bg=self.dark_mode_colors['bg'], fg='white')
                widget.itemconfig(current_index, bg='white', fg='black')
                last_hovered_index[0] = current_index

        def reset_listbox_colors(event):
            widget = event.widget
            for i in range(widget.size()):
                if i not in widget.curselection():
                    widget.itemconfig(i, bg=self.dark_mode_colors['bg'], fg='white')
            last_hovered_index[0] = -1
        version_listbox.bind('<Motion>', on_listbox_hover)
        version_listbox.bind('<Leave>', reset_listbox_colors)
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10, padx=10, fill=tk.X)
        ttk.Button(button_frame, text='Install', command=lambda: on_select(version_listbox, dialog, selected_mod, versions)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text='Cancel', command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        def on_select(listbox, parent, mod, all_versions):
            selection = listbox.curselection()
            if selection:
                selected_version = all_versions[selection[0]]
                parent.destroy()
                self.install_specific_version(mod, selected_version)

    def show_discord_prompt(self):
        if not self.settings.get('discord_prompt_shown2', False):
            if (response := messagebox.askyesno('Join Our Discord Community', "Welcome to Buoy!\n\nWe have a new Discord server! Even if you were in the old one, you'll want to join this new community for:\n• Troubleshooting assistance\n• Latest updates and announcements\n• Mod discussions and sharing\n• Direct support from the developer\n\nWould you like to join our new Discord now?", icon='info')):
                webbrowser.open('https://discord.gg/7HdZJZbkhw')
            self.settings['discord_prompt_shown2'] = True
            self.save_settings()

    def save_mod_status(self, mod):
        if mod.get('third_party', False):
            mod_folder = os.path.join(self.mods_dir, '3rd_party', mod['id'])
        else:
            mod_folder = os.path.join(self.mods_dir, mod['id'])
        mod_json_path = os.path.join(mod_folder, 'mod_info.json')
        if not os.path.exists(mod_folder):
            os.makedirs(mod_folder)
        try:
            with open(mod_json_path, 'w') as f:
                json.dump(mod, f, indent=2)
            logging.info(f"Saved mod status for {mod['title']} (ID: {mod['id']})")
        except Exception as e:
            error_message = f"Failed to save mod status for {mod['title']} (ID: {mod['id']}): {str(e)}"
            self.set_status(error_message)
            logging.info(error_message)
        self.save_mod_cache()

    def update_installed_filter_options(self):
        filter_options = ['All', 'Enabled', 'Disabled']
        categories = set()
        for mod in self.installed_mods:
            categories.update(mod.get('categories', []))
        filter_options.extend(sorted(categories))
        current_value = self.installed_category.get()
        self.installed_category['values'] = filter_options
        if current_value in filter_options:
            self.installed_category.set(current_value)
        else:
            self.installed_category.set('All')

    def load_mod_cache(self):
        try:
            if os.path.exists(self.mod_cache_file):
                with open(self.mod_cache_file, 'r') as f:
                    self.mod_cache = json.load(f)
            else:
                self.mod_cache = {}
        except Exception as e:
            error_message = f'Failed to load mod cache: {str(e)}'
            self.set_status(error_message)
            self.mod_cache = {}

    def update_mod_details(self, event):
        try:
            listbox = event.widget
            selection = listbox.curselection()
            if not selection:
                return
            selected_title = listbox.get(selection[0])
            selected_title = re.sub('^[✅❌]\\s*(?:\\[3rd\\]\\s*)?', '', selected_title)
            if selected_title.startswith('--'):
                self._show_category_details(selected_title)
                return
            backend_title = self.get_backend_name(selected_title)
            mod = self.find_mod_by_title(backend_title)
            self.mod_details.config(state='normal')
            self.mod_details.delete('1.0', tk.END)
            for widget in self.mod_details_frame.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.destroy()
            is_installed = listbox == self.installed_listbox
            title_text = f"{self.get_display_name(mod['title'])} v{mod.get('version', '?')}\n"
            title_text += f"by {mod.get('author', 'Unknown')}\n\n"
            self.mod_details.insert(tk.END, title_text, 'header')
            self.mod_details.tag_config('header', font=('TkDefaultFont', 10, 'bold'))
            if is_installed:
                if 'updated_on' in mod:
                    updated = datetime.fromtimestamp(mod['updated_on'])
                    time_diff = datetime.now() - updated
                    if time_diff.days > 0:
                        time_str = f'{time_diff.days} days ago'
                    elif time_diff.seconds // 3600 > 0:
                        time_str = f'{time_diff.seconds // 3600} hours ago'
                    else:
                        time_str = f'{time_diff.seconds // 60} minutes ago'
                    self.mod_details.insert(tk.END, f'📅 Installed {time_str}\n')
                if (categories := mod.get('categories', [])):
                    category_display = []
                    category_emojis = {'Mods': '🎯', 'Cosmetics': '🎨', 'Tools': '🔨', 'Libraries': '📖', 'Misc': '📦', 'Client Side': '💻', 'Server Side': '🖥', 'Fish': '🐟', 'Species': '🦈', 'Maps': '🗺'}
                    for category in categories:
                        emoji = category_emojis.get(category, '📦')
                        category_display.append(f'{emoji} {category}')
                    self.mod_details.insert(tk.END, ' • '.join(category_display) + '\n')
                if mod.get('description'):
                    self.mod_details.insert(tk.END, '\n📝 Description\n', 'subheader')
                    desc = strip_tags(mod['description']) or mod['description']
                    self.mod_details.insert(tk.END, f'{desc}\n')
                if mod.get('thunderstore_id'):
                    self.mod_details.insert(tk.END, '\n🔗 Links\n', 'subheader')
                    creator, mod_name = mod['thunderstore_id'].split('-', 1)
                    thunderstore_url = f'https://thunderstore.io/c/webfishing/p/{creator}/{mod_name}/'
                    self.mod_details.insert(tk.END, '• View on Thunderstore: ')
                    self.mod_details.insert(tk.END, thunderstore_url, 'link')
                    self.mod_details.insert(tk.END, '\n')
                    link_color = 'cyan' if self.dark_mode.get() else 'blue'
                    self.mod_details.tag_config('link', foreground=link_color, underline=1)
                    self.mod_details.tag_bind('link', '<Button-1>', lambda e: webbrowser.open(thunderstore_url))
            else:
                stats = []
                if 'last_updated' in mod:
                    updated = self._format_timestamp(mod['last_updated'])
                    if updated:
                        stats.append(f'📅 Updated {updated}')
                if 'downloads' in mod:
                    stats.append(f"🌐 {mod['downloads']:,} downloads")
                if 'likes' in mod:
                    stats.append(f"👍 {mod['likes']:,} likes")
                if stats:
                    self.mod_details.insert(tk.END, ' • '.join(stats) + '\n')
                if (categories := mod.get('categories', [])):
                    category_display = []
                    category_emojis = {'Mods': '🎯', 'Cosmetics': '🎨', 'Tools': '🔨', 'Libraries': '📖', 'Misc': '📦', 'Client Side': '💻', 'Server Side': '🖥', 'Fish': '🐟', 'Species': '🦈', 'Maps': '🗺'}
                    for category in categories:
                        emoji = category_emojis.get(category, '📦')
                        category_display.append(f'{emoji} {category}')
                    self.mod_details.insert(tk.END, ' • '.join(category_display) + '\n')
                warnings = []
                if mod.get('has_nsfw_content', False):
                    warnings.append('🔞 NSFW')
                if mod.get('is_deprecated', False):
                    warnings.append('⚠️ Deprecated')
                if mod.get('third_party', False):
                    warnings.append('⚠️ Third Party Mod')
                if warnings:
                    self.mod_details.insert(tk.END, ' • '.join(warnings) + '\n\n')
                elif stats or categories:
                    self.mod_details.insert(tk.END, '\n')
                if mod.get('third_party', False):
                    self.mod_details.insert(tk.END, '📝 Description\n', 'subheader')
                    if mod.get('description'):
                        self.mod_details.insert(tk.END, f"{mod['description']}\n\n")
                    else:
                        self.mod_details.insert(tk.END, f"We don't know much about the 3rd party mod {selected_title}, but we're sure it's great!\n\n")
                elif mod.get('description'):
                    desc = strip_tags(mod['description']) or mod['description']
                    self.mod_details.insert(tk.END, '📝 Description\n', 'subheader')
                    self.mod_details.insert(tk.END, f'{desc}\n\n')
                if (deps := mod.get('dependencies', [])):
                    visible_deps = [dep for dep in deps if not dep.startswith('NotNet-GDWeave')]
                    if visible_deps:
                        self.mod_details.insert(tk.END, '⚡ Dependencies\n', 'subheader')
                        self.mod_details.tag_config('subheader', font=('TkDefaultFont', 9, 'bold'))
                        for dep in visible_deps:
                            parts = dep.split('-') if dep else []
                            if len(parts) == 3:
                                creator, title, version = parts
                                formatted_dep = f'{title} ({version}) by {creator}'
                                self.mod_details.insert(tk.END, f'• {formatted_dep}\n')
                            else:
                                self.mod_details.insert(tk.END, f'• {dep}\n')
                        self.mod_details.insert(tk.END, '\n')
                self.mod_details.insert(tk.END, '🔗 Links\n', 'subheader')
                if mod.get('thunderstore_id'):
                    creator, mod_name = mod['thunderstore_id'].split('-', 1)
                    thunderstore_url = f'https://thunderstore.io/c/webfishing/p/{creator}/{mod_name}/'
                    self.mod_details.insert(tk.END, '• View on Thunderstore: ')
                    self.mod_details.insert(tk.END, thunderstore_url, 'link')
                    self.mod_details.insert(tk.END, '\n')
                    link_color = 'cyan' if self.dark_mode.get() else 'blue'
                    self.mod_details.tag_config('link', foreground=link_color, underline=1)
                    self.mod_details.tag_bind('link', '<Button-1>', lambda e: webbrowser.open(thunderstore_url))
                if mod.get('website'):
                    self.mod_details.insert(tk.END, '• Website: ')
                    self.mod_details.insert(tk.END, mod['website'], 'link2')
                    self.mod_details.insert(tk.END, '\n')
                    link_color = 'cyan' if self.dark_mode.get() else 'blue'
                    self.mod_details.tag_config('link2', foreground=link_color, underline=1)
                    self.mod_details.tag_bind('link2', '<Button-1>', lambda e: webbrowser.open(mod['website']))
        except Exception as e:
            error_msg = f"Error: Unable to find mod details for '{selected_title}'. Error: {str(e)}"
            self.mod_details.config(state='normal')
            self.mod_details.delete('1.0', tk.END)
            self.mod_details.insert(tk.END, error_msg)
            logging.error(f'Error in update_mod_details: {error_msg}')
            self.mod_details.config(state='disabled')
        self.mod_details.config(state='disabled')

    def is_thunderstore_mod_enabled(self, thunderstore_id):
        try:
            for mod in self.installed_mods:
                if mod.get('third_party', False):
                    continue
                if mod.get('thunderstore_id') == thunderstore_id and mod.get('enabled', False):
                    return True
            for mod_folder in os.listdir(self.mods_dir):
                if mod_folder == '3rd_party':
                    continue
                mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        if mod_info.get('thunderstore_id') == thunderstore_id and mod_info.get('enabled', False):
                            return True
            return False
        except Exception as e:
            logging.error(f'Error checking if thunderstore mod {thunderstore_id} is enabled: {str(e)}')
            return False

    def get_default_settings(self):
        return {'auto_update': True, 'windowed_mode': True, 'notifications': True, 'theme': 'system', 'game_path': '', 'show_nsfw': False, 'show_deprecated': False, 'discord_prompt_shown': False, 'discord_prompt_shown2': False, 'no_logging': False, 'error_reporting_prompted': False, 'auto_backup': True, 'gdweave_version': 'Unknown', 'blacklisted_versions': {}, 'available_sort_by': 'Last Updated', 'installed_sort_by': 'Recently Installed', 'dark_mode': True}

    def verify_installation(self):
        try:
            game_path = self.game_path_entry.get()
            exe_name = 'webfishing.exe' if platform.system() == 'Windows' else 'webfishing'
            exe_path = os.path.join(game_path, exe_name)
            if os.path.exists(game_path) and os.path.isfile(exe_path):
                self.set_status('Game installation verified successfully!')
            else:
                self.set_status(f'Invalid game installation path or {exe_name} not found!')
        except Exception as e:
            error_message = f'Error verifying game installation: {str(e)}'
            self.set_status(error_message)

    def load_settings(self):
        settings_path = os.path.join(self.app_data_dir, 'settings.json')
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                logging.error(f'Failed to load settings: {e}')
                self.settings = self.get_default_settings()
        else:
            self.settings = self.get_default_settings()
            logging.info('No settings file found, using default settings')
        defaults = self.get_default_settings()
        for key, value in defaults.items():
            if key not in self.settings:
                self.settings[key] = value
        self.print_settings()

    def save_settings(self):
        self.settings.update({'auto_update': self.auto_update.get(), 'windowed_mode': self.windowed_mode.get(), 'notifications': self.notifications.get(), 'theme': self.theme.get(), 'game_path': self.game_path_entry.get(), 'show_nsfw': self.show_nsfw.get(), 'show_deprecated': self.show_deprecated.get(), 'auto_backup': self.auto_backup.get(), 'suppress_mod_warning': self.suppress_mod_warning.get()})
        settings_path = os.path.join(self.app_data_dir, 'settings.json')
        with open(settings_path, 'w') as f:
            json.dump(self.settings, f)
        self.set_status('Settings saved successfully!')
        logging.info('Settings saved:', self.settings)

    def refresh_mod_lists(self):
        if hasattr(self, 'available_listbox'):
            current_items = list(self.available_listbox.get(0, tk.END))
            if not current_items:
                self.load_available_mods()
        self.installed_mods = self.get_installed_mods()
        if hasattr(self, 'installed_listbox'):
            self.installed_listbox.delete(0, tk.END)
            for mod in self.installed_mods:
                status = '✅' if mod.get('enabled', True) else '❌'
                third_party = '[3rd] ' if mod.get('third_party', False) else ''
                display_title = self.get_display_name(mod['title'])
                display_text = f'{status} {third_party}{display_title}'.strip()
                self.installed_listbox.insert(tk.END, display_text)
            if hasattr(self, 'installed_frame'):
                self.installed_frame.configure(text=f'Installed Mods ({len(self.installed_mods)})')
        self.save_mod_cache()
        self.filter_available_mods()
        self.filter_installed_mods()
        if hasattr(self, 'available_frame'):
            visible_mods = self.available_listbox.size()
            total_mods = len(self.available_mods)
            if visible_mods != total_mods:
                self.available_frame.configure(text=f'Thunderstore Mods ({visible_mods}/{total_mods})')
            else:
                self.available_frame.configure(text=f'Thunderstore Mods ({total_mods})')

    def clean_mod_cache(self):
        updated_cache = {mod_id: mod_info for mod_id, mod_info in self.mod_cache.items() if self.mod_exists({'id': mod_id, 'third_party': mod_info.get('third_party', False)})}
        self.mod_cache = updated_cache
        self.save_mod_cache()

    def get_installed_mods(self):
        installed_mods = []
        for mod_folder in os.listdir(self.mods_dir):
            if mod_folder != '3rd_party':
                mod_info_path = os.path.join(self.mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        installed_mods.append(mod_info)
        third_party_mods_dir = os.path.join(self.mods_dir, '3rd_party')
        if os.path.exists(third_party_mods_dir):
            for mod_folder in os.listdir(third_party_mods_dir):
                mod_info_path = os.path.join(third_party_mods_dir, mod_folder, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_info['third_party'] = True
                        installed_mods.append(mod_info)
        return installed_mods

    def download_and_install_mod(self, mod, install=True):
        thread = threading.Thread(target=self._download_and_install_mod_thread, args=(mod, install))
        thread.daemon = True
        thread.start()

    def _download_and_install_mod_thread(self, mod, install=True):
        download_temp_dir = None
        try:
            self.mod_downloading = True
            self.set_status_safe(f"Downloading {mod['title']}...")
            temp_dir = os.path.join(self.app_data_dir, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            download_temp_dir = os.path.join(temp_dir, f'download_{uuid.uuid4().hex}')
            os.makedirs(download_temp_dir)
            try:
                max_retries = 3
                retry_count = 0
                while True:
                    try:
                        response = requests.head(mod['download'], timeout=30)
                        file_size = int(response.headers.get('content-length', 0))
                        if file_size == 0:
                            response = requests.get(mod['download'], stream=True, timeout=30)
                            file_size = int(response.headers.get('content-length', 0))
                        break
                    except Exception as e:
                        if 'ConnectionResetError' in str(e) or '10054' in str(e):
                            retry_count += 1
                            if retry_count >= max_retries:
                                self.root.after(0, lambda: messagebox.showerror('Download Error', 'Thunderstore appears to be having issues. Please try again in a few minutes.'))
                                raise ValueError('Thunderstore connection issues - please try again later')
                            time.sleep(1)
                            continue
                        raise
                logging.info(f"Downloading mod {mod['title']} ({file_size / 1024 / 1024:.1f}MB)")
                if file_size > 52428800:
                    warning_msg = f"WARNING: {mod['title']} is {file_size / 1024 / 1024:.1f}MB which exceeds the recommended 50MB limit.\n\nThis is unusually large for a mod. Large mods are not recommended as they may:\n\n• Take a long time to download\n• Use excessive system memory\n• Cause Buoy to stop responding\n\nConsider finding a smaller alternative mod.\n\nDo you want to continue anyway?"
                    if not messagebox.askyesno('Excessive File Size', warning_msg, icon='warning'):
                        raise ValueError('Download cancelled - file too large')
                retry_count = 0
                while True:
                    try:
                        response = requests.get(mod['download'], timeout=30)
                        response.raise_for_status()
                        break
                    except Exception as e:
                        if 'ConnectionResetError' in str(e) or '10054' in str(e):
                            retry_count += 1
                            if retry_count >= max_retries:
                                self.root.after(0, lambda: messagebox.showerror('Download Error', 'Thunderstore appears to be having issues. Please try again in a few minutes.'))
                                raise ValueError('Thunderstore connection issues - please try again later')
                            time.sleep(1)
                            continue
                        raise
            except requests.Timeout:
                raise ValueError('Download timed out - please try again')
            except requests.RequestException as e:
                raise ValueError(f'Download failed: {str(e)}')
            zip_path = os.path.join(download_temp_dir, f"{mod['id']}.zip")
            try:
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
            except IOError as e:
                raise ValueError(f'Failed to save downloaded file: {str(e)}')
            extract_dir = os.path.join(download_temp_dir, 'extracted')
            os.makedirs(extract_dir)
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            except zipfile.BadZipFile:
                raise ValueError('Downloaded file is not a valid zip archive')
            except Exception as e:
                raise ValueError(f'Failed to extract zip file: {str(e)}')
            manifest_path = None
            manifest = None
            for root, dirs, files in os.walk(extract_dir):
                if 'manifest.json' in files:
                    try:
                        with open(os.path.join(root, 'manifest.json'), 'r') as f:
                            manifest_data = json.load(f)
                            if manifest_data.get('Id'):
                                manifest_path = os.path.join(root, 'manifest.json')
                                manifest = manifest_data
                                break
                    except json.JSONDecodeError:
                        continue
                    except IOError:
                        continue
            if not manifest_path or not manifest:
                raise ValueError(f"{mod['title']} is likely not an installable mod!")
            mod_id = manifest.get('Id')
            if not mod_id:
                raise ValueError(f"{mod['title']} is likely not an installable mod!")
            mod_dir = os.path.join(self.mods_dir, mod_id)
            if os.path.exists(mod_dir):
                try:
                    shutil.rmtree(mod_dir)
                except Exception as e:
                    raise ValueError(f'Failed to remove existing mod directory: {str(e)}')
            try:
                manifest_parent = os.path.dirname(manifest_path)
                if manifest_parent != extract_dir:
                    shutil.move(manifest_parent, mod_dir)
                else:
                    shutil.move(extract_dir, mod_dir)
            except Exception as e:
                raise ValueError(f'Failed to move mod files: {str(e)}')
            existing_enabled = True
            for installed_mod in self.installed_mods:
                if installed_mod.get('id') == mod_id:
                    existing_enabled = installed_mod.get('enabled', True)
                    break
            mod_info = {'id': mod_id, 'title': manifest.get('Name', mod['title']), 'author': manifest.get('Author', mod['author']), 'description': manifest.get('Description', mod['description']), 'version': manifest.get('Version', mod['version']), 'enabled': existing_enabled, 'thunderstore_id': mod['thunderstore_id'], 'categories': mod.get('categories', []), 'downloads': mod.get('downloads', 0), 'likes': mod.get('likes', 0), 'last_updated': mod.get('last_updated', ''), 'is_deprecated': mod.get('is_deprecated', False), 'has_nsfw_content': mod.get('has_nsfw_content', False), 'website': mod.get('website', ''), 'updated_on': int(time.time()), 'dependencies': manifest.get('Dependencies', [])}
            try:
                mod_info_path = os.path.join(mod_dir, 'mod_info.json')
                with open(mod_info_path, 'w') as f:
                    json.dump(mod_info, f, indent=2)
            except Exception as e:
                raise ValueError(f'Failed to create mod_info.json: {str(e)}')
            self.installed_mods.append(mod_info)
            if mod_info['enabled']:
                try:
                    self.copy_mod_to_game(mod_info)
                except Exception as e:
                    raise ValueError(f'Failed to copy mod to game directory: {str(e)}')
            self.set_status_safe(f"Successfully installed {mod['title']}")
            logging.info(f"Installed mod: {mod['title']} (ID: {mod_id})")
            if install:
                self.root.after(0, self.installation_complete, mod_info)
            else:
                return mod_info
        except Exception as e:
            error_message = f"Failed to install {mod['title']}: {str(e)}"
            self.set_status_safe(error_message)
            logging.error(error_message)
            if install:
                self.root.after(0, self.installation_failed, error_message)
            else:
                raise ValueError(error_message)
        finally:
            self.mod_downloading = False
            if download_temp_dir and os.path.exists(download_temp_dir):
                try:
                    shutil.rmtree(download_temp_dir)
                except Exception as e:
                    logging.error(f'Failed to clean up temp directory: {str(e)}')

    def installation_complete(self, mod_info):
        self.set_status_safe(f"Mod {mod_info['title']} version {mod_info['version']} installed successfully!")
        self.refresh_mod_lists()
        self.copy_mod_to_game(mod_info)

    def download_file(self, url, destination):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            return True
        except Exception as e:
            error_message = f'Failed to download file from {url}: {str(e)}'
            logging.error(error_message)
            raise ValueError(error_message)

    def install_downloaded_mod(self, mod_info):
        mod_path = os.path.join(self.mods_dir, mod_info['id'])
        os.makedirs(mod_path, exist_ok=True)
        with open(os.path.join(mod_path, 'mod_info.json'), 'w') as f:
            json.dump(mod_info, f, indent=2)
        self.copy_mod_to_game(mod_info)
        self.installed_mods.append(mod_info)
        self.set_status(f"Installed mod: {mod_info['title']}")
        self.installation_complete(mod_info)

    def verify_appdata_mods(self):
        logging.info('Verifying contents of app data mods directory')
        for mod_id in os.listdir(self.mods_dir):
            mod_path = os.path.join(self.mods_dir, mod_id)
            if os.path.isdir(mod_path):
                logging.info(f'Mod directory: {mod_id}')
                for root, dirs, files in os.walk(mod_path):
                    for file in files:
                        logging.info(f'  - {os.path.join(os.path.relpath(root, mod_path), file)}')

    def installation_complete(self, mod_info):
        self.set_status(f"Mod {mod_info['title']} version {mod_info['version']} installed successfully!")
        self.refresh_mod_lists()
        self.verify_appdata_mods()
        self.copy_mod_to_game(mod_info)

    def installation_failed(self, error_message):
        self.set_status_safe(f'Failed to install mod: {error_message}')

    def get_mod_version(self, mod):
        try:
            url = mod['download']
            parsed_url = urlparse(url)
            if 'github.com' in parsed_url.netloc:
                repo_owner, repo_name = parsed_url.path.split('/')[1:3]
                api_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest'
            else:
                base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
                path_parts = parsed_url.path.split('/')
                repo_owner, repo_name = path_parts[1:3]
                api_url = f'{base_url}/api/v1/repos/{repo_owner}/{repo_name}/releases/latest'
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            version = re.search('v?(\\d+\\.\\d+\\.\\d+)', data['tag_name'])
            version = version[1] if version else data['tag_name']
            return {'version': version, 'published_at': data['published_at']}
        except Exception as e:
            logging.info(f'Failed to get version: {str(e)}')
            return {'version': 'Unknown', 'published_at': None}

    def check_for_updates(self, silent=False):
        try:
            self.set_status_safe('Checking for mod and GDWeave updates...')
            updates_available = False
            if not self.installed_mods:
                self.set_status_safe('No mods installed. Skipping mod update check.')
            else:
                mods_to_update = []
                for installed_mod in self.installed_mods:
                    for available_mod in self.available_mods:
                        if installed_mod['title'].lower() == available_mod['title'].lower():
                            try:
                                if self.is_update_available(installed_mod, available_mod):
                                    updates_available = True
                                    mods_to_update.append({'installed': installed_mod, 'available': available_mod})
                            except Exception as e:
                                error_message = f"Error checking update for mod {installed_mod['title']}: {str(e)}"
                                self.set_status_safe(error_message)
                            break
                if mods_to_update:
                    update_window = tk.Toplevel(self.root)
                    update_window.title('Updates Available')
                    update_window.geometry('600x600')
                    icon_path = get_resource_path('images/icon.ico')
                    update_window.configure(bg=self.dark_mode_colors['bg'])
                    mods_listbox = tk.Listbox(update_window, selectmode=tk.MULTIPLE, bg=self.dark_mode_colors['bg'], fg=self.dark_mode_colors['fg'])
                    mods_listbox.pack(fill='both', expand=True)
                    for mod in mods_to_update:
                        installed = mod['installed']
                        available = mod['available']
                        mods_listbox.insert('end', f"{installed['title']} (Current version: {installed.get('version', 'Unknown')}, New version: {available.get('version', 'Unknown')})")

                    def update_selected_mods():
                        selected_mods = mods_listbox.curselection()
                        for index in selected_mods:
                            mod = mods_to_update[index]
                            self.download_and_install_mod(mod['available'])
                        update_window.destroy()
                    update_button = tk.Button(update_window, text='Update Selected Mods', command=update_selected_mods, bg=self.dark_mode_colors['button_bg'], fg=self.dark_mode_colors['button_fg'])
                    update_button.pack(pady=10, padx=10)
                    cancel_button = tk.Button(update_window, text='Cancel', command=update_window.destroy, bg=self.dark_mode_colors['button_bg'], fg=self.dark_mode_colors['button_fg'])
                    cancel_button.pack(pady=10, padx=10)
                else:
                    # Show a message when no updates are available
                    if not silent:
                        tk.messagebox.showinfo("No Updates", "All installed mods are up to date.")
                    self.set_status_safe("All installed mods are up to date.")
        except Exception as e:
            error_message = f'Error checking for updates: {str(e)}'
            self.set_status_safe(error_message)


    def is_update_available(self, installed_mod, available_mod):
        """Check if an update is available for a mod"""
        try:
            mod_id = installed_mod.get('thunderstore_id')
            if not mod_id:
                return False
            blacklisted = self.settings.get('blacklisted_versions', {}).get(mod_id, [])
            if available_mod.get('version') in blacklisted:
                logging.info(f"Skipping blacklisted version {available_mod.get('version')} for {installed_mod.get('title')}")
                return False
            logging.info(f"Checking for updates - installed mod: {installed_mod.get('title')}, available mod: {available_mod.get('title')}")

            def get_base_id(thunderstore_id):
                if not thunderstore_id:
                    logging.debug(f'No thunderstore_id provided')
                    return ''
                version_pattern = '-\\d+\\.\\d+\\.\\d+$'
                base_id = re.sub(version_pattern, '', thunderstore_id)
                logging.debug(f"Converting thunderstore_id '{thunderstore_id}' to base_id '{base_id}'")
                return base_id
            installed_base_id = get_base_id(installed_mod.get('thunderstore_id', ''))
            available_base_id = get_base_id(available_mod.get('thunderstore_id', ''))
            logging.info(f'Comparing base IDs - Installed: {installed_base_id}, Available: {available_base_id}')
            if not installed_base_id or not available_base_id or installed_base_id != available_base_id:
                logging.info('No update needed - Different or missing thunderstore IDs')
                return False

            def parse_version(version_str):
                logging.debug(f'Parsing version string: {version_str}')
                match = re.search('(\\d+)\\.(\\d+)\\.(\\d+)', version_str or '0.0.0')
                if not match:
                    logging.debug('No version match found, using default [0,0,0]')
                    return [0, 0, 0]
                version = [int(x) for x in match.groups()]
                logging.debug(f'Parsed version: {version}')
                return version
            installed_version = parse_version(installed_mod.get('version'))
            available_version = parse_version(available_mod.get('version'))
            logging.info(f'Comparing versions - Installed: {installed_version}, Available: {available_version}')
            for i in range(3):
                if available_version[i] > installed_version[i]:
                    logging.info(f'Update available - Component {i} is newer ({available_version[i]} > {installed_version[i]})')
                    return True
                elif available_version[i] < installed_version[i]:
                    logging.info(f'No update needed - Component {i} is older ({available_version[i]} < {installed_version[i]})')
                    return False
            logging.info('No update needed - Versions are identical')
            return False
        except Exception as e:
            error_msg = f"Error checking update for mod {installed_mod.get('title')}: {str(e)}"
            logging.error(error_msg)
            logging.error(f'Full traceback: {traceback.format_exc()}')
            return False

    def save_mod_cache(self):
        try:
            mod_cache = {mod['id']: {'title': mod['title'], 'version': mod.get('version', 'Unknown'), 'enabled': mod.get('enabled', True), 'third_party': mod.get('third_party', False)} for mod in self.installed_mods}
            with open(self.mod_cache_file, 'w') as f:
                json.dump(mod_cache, f, indent=2)
            logging.info(f'Mod cache saved. Total mods cached: {len(mod_cache)}')
        except Exception as e:
            error_message = f'Failed to save mod cache: {str(e)}'
            self.set_status(error_message)
            logging.info(error_message)

    def copy_mod_to_game(self, mod_info):
        mod_id = mod_info['id']
        is_third_party = mod_info.get('third_party', False)
        if is_third_party:
            source_dir = os.path.join(self.mods_dir, '3rd_party', mod_id)
        else:
            source_dir = os.path.join(self.mods_dir, mod_id)
        logging.info(f"copy_mod_to_game called for mod '{mod_info['title']}' (ID: {mod_id}, Third Party: {is_third_party})")
        logging.info(f'Source directory: {source_dir}')
        if not os.path.exists(source_dir):
            logging.error(f"Source directory for mod '{mod_info['title']}' (ID: {mod_id}) not found.")
            return
        logging.info(f'Contents of source directory {source_dir} before copying:')
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                logging.info(os.path.join(root, file))
        if not self.settings.get('game_path'):
            logging.error('Game path not set. Cannot copy mod to game.')
            return
        destination_dir = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods', mod_id)
        logging.info(f'Destination directory: {destination_dir}')
        try:
            if os.path.exists(destination_dir):
                logging.info(f'Removing existing destination directory: {destination_dir}')
                shutil.rmtree(destination_dir)
            logging.info(f'Copying from {source_dir} to {destination_dir}')
            shutil.copytree(source_dir, destination_dir)
            logging.info(f'Contents of destination directory {destination_dir} after copying:')
            for root, dirs, files in os.walk(destination_dir):
                for file in files:
                    logging.info(os.path.join(root, file))
            logging.info(f"Mod '{mod_info['title']}' (ID: {mod_id}) copied successfully to game directory.")
        except Exception as e:
            logging.error(f"Error copying mod '{mod_info['title']}' (ID: {mod_id}) to game directory: {str(e)}")
            logging.error(traceback.format_exc())

    def remove_mod_from_game(self, mod):
        gdweave_mods_path = os.path.join(self.settings['game_path'], 'GDWeave', 'Mods')
        mod_path_in_game = os.path.join(gdweave_mods_path, mod['id'])
        if os.path.exists(mod_path_in_game):
            logging.info(f'Removing mod from game: {mod_path_in_game}')
            shutil.rmtree(mod_path_in_game)
            logging.info(f"Successfully removed mod '{mod['title']}' (ID: {mod['id']}) from game directory.")
        else:
            logging.info(f"Mod '{mod['title']}' (ID: {mod['id']}) not found in game directory.")

    def print_settings(self):
        settings_to_print = self.settings.copy()
        if 'user_id' in settings_to_print:
            settings_to_print['user_id'] = '********-****-****-****-************'
        logging.info('Current settings:')
        for key, value in settings_to_print.items():
            logging.info(f'  {key}: {value}')

    def browse_game_directory(self):
        if (directory := filedialog.askdirectory()):
            self.game_path_entry.delete(0, tk.END)
            self.game_path_entry.insert(0, directory)
            self.save_game_path()

    def save_game_path(self):
        new_path = self.game_path_entry.get()
        if os.path.exists(new_path):
            self.settings['game_path'] = new_path
            self.save_settings()
            self.set_status(f'Game path updated to: {new_path}')
            logging.info(f'Game path updated to: {new_path}')
            self.update_setup_status()
        else:
            self.set_status('Invalid game path. Please enter a valid directory.')
            logging.info('Invalid game path entered.')

    def get_display_name(self, mod_title):
        return mod_title.replace('_', ' ')

    def get_backend_name(self, display_title):
        return display_title.replace(' ', '_')

    def handle_filter_toggle(self, filter_type):
        self.save_settings()
        current_category = self.available_category.get()
        self.available_mods = []
        self.load_available_mods()
        categories = {'All'}
        for mod in self.available_mods:
            categories.update(mod.get('categories', []))
        self.available_category['values'] = sorted(list(categories))
        mods_in_category = any((current_category in mod.get('categories', []) for mod in self.available_mods)) if current_category != 'All' else True
        if current_category in categories and mods_in_category:
            self.available_category.set(current_category)
        else:
            self.available_category.set('All')
        self.filter_available_mods()

    def load_available_mods(self):
        try:
            response = requests.get('https://thunderstore.io/c/webfishing/api/v1/package/')
            thunderstore_mods = response.json()
            mod_map = {}
            for mod in thunderstore_mods:
                is_deprecated = mod.get('is_deprecated', False)
                is_nsfw = mod.get('has_nsfw_content', False)
                if is_deprecated and (not self.show_deprecated.get()) or (is_nsfw and (not self.show_nsfw.get())):
                    continue
                if not mod['versions']:
                    continue
                latest_version = mod['versions'][0]
                mod_info = {'title': mod['name'], 'thunderstore_id': f"{mod['owner']}-{mod['name']}", 'id': f"{mod['owner']}-{mod['name']}", 'description': latest_version['description'], 'version': latest_version['version_number'], 'download': latest_version['download_url'], 'categories': mod['categories'], 'author': mod['owner'], 'dependencies': latest_version['dependencies'], 'website': latest_version.get('website_url', ''), 'downloads': latest_version.get('downloads', 0), 'likes': mod.get('rating_score', 0), 'last_updated': mod.get('date_updated', ''), 'is_deprecated': is_deprecated, 'has_nsfw_content': is_nsfw, 'date_updated': mod['date_updated']}
                if len(latest_version['dependencies']) > 5:
                    mod_info['categories'].append('Modpacks')
                if mod['name'] in mod_map:
                    existing = mod_map[mod['name']]
                    if existing['is_deprecated'] and (not is_deprecated):
                        mod_map[mod['name']] = mod_info
                    elif existing['is_deprecated'] == is_deprecated:
                        if mod['date_updated'] > existing['date_updated']:
                            mod_map[mod['name']] = mod_info
                else:
                    mod_map[mod['name']] = mod_info
            self.available_mods = list(mod_map.values())
            categories = set()
            for mod in self.available_mods:
                categories.update(mod.get('categories', []))
            self.available_category['values'] = ['All'] + sorted(list(categories))
            self.available_category.set('All')
            self.update_available_mods_list()
        except requests.RequestException as e:
            self.set_status(f'Failed to load mods: {str(e)}')

    def mod_id_exists(self, mod_id):
        if os.path.exists(os.path.join(self.mods_dir, mod_id)):
            return True
        if os.path.exists(os.path.join(self.mods_dir, '3rd_party', mod_id)):
            return True
        return any((mod.get('id') == mod_id for mod in self.installed_mods))

    def mod_exists(self, mod):
        if mod.get('id') == 'separator':
            return True
        if 'id' not in mod:
            return True
        if mod.get('third_party', False):
            mod_path = os.path.join(self.mods_dir, '3rd_party', mod['id'])
        else:
            mod_path = os.path.join(self.mods_dir, mod['id'])
        return os.path.exists(mod_path)

    def load_third_party_mods(self):
        third_party_mods_dir = os.path.join(self.mods_dir, '3rd_party')
        if not os.path.exists(third_party_mods_dir):
            return
        for mod_folder in os.listdir(third_party_mods_dir):
            mod_path = os.path.join(third_party_mods_dir, mod_folder)
            if os.path.isdir(mod_path):
                mod_info_path = os.path.join(mod_path, 'mod_info.json')
                if os.path.exists(mod_info_path):
                    with open(mod_info_path, 'r') as f:
                        mod_info = json.load(f)
                        mod_info['third_party'] = True
                        self.available_mods.append(mod_info)
if __name__ == '__main__':
    root = tk.Tk()
    app = BuoyUI(root)
    root.mainloop()