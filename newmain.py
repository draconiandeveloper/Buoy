from Buoy import (
    _create_mod_manager_tab
)

from Buoy import FileIO
from Buoy import NetIO
import threading
import logging
import tkinter
import queue
import os

class BuoyUI:
    def __init__(self, root):
        self.root = root
        self.fileio = FileIO(None)

        # self.setup_logging()
        self.gui_queue, self.gdweave_queue = [queue.Queue(), queue.Queue()]

        self.load_settings()
        themefile = FileIO(os.path.join(os.path.dirname(__file__), 'theme.yml'))
        self.dark_mode_colors = themefile.parse_yaml_theme()
        self.dark_mode = tkinter.BooleanVar(value=self.settings.get('dark_mode', True))

        version = '1.0.3'
        self.root.title(f'Buoy v{version}')
        if self.settings.get('windowed_mode', True):
            window_width, window_height = [800, 640]
            x = (self.root.winfo_screenwidth() - window_width) // 2
            y = (self.root.winfo_screenheight() - window_height) // 2
            self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
        else: self.root.state('zoomed')
        self.root.minsize(800, 640)


    
    def get_default_settings(self):
        return {
            'auto_update': True,
            'windowed_mode': True,
            'notifications': True,
            'theme': 'system',
            'game_path': '',
            'show_nsfw': False,
            'show_deprecated': False,
            'discord_prompt_shown': False,
            'discord_prompt_shown2': False,
            'no_logging': False,
            'error_reporting_prompted': False,
            'auto_backup': True,
            'gdweave_version': 'Unknown',
            'blacklisted_versions': {},
            'available_sort_by': 'Last Updated',
            'installed_sort_by': 'Recently Installed',
            'dark_mode': True
        }

    def load_settings(self):
        settings_path = os.path.join(self.fileio.appdata, 'settings.json')
        if not os.path.exists(settings_path):
            self.settings = self.get_default_settings()
            logging.info('No settings file found, using default settings')
            return
        
        settings_file = FileIO(settings_path)
        try:
            self.settings = settings_file.load_json_data()
        except Exception as e:
            logger.error(f'Failed to load settings: {e}')
            self.settings = self.get_default_settings()
    
    #
    # GUI Elements
    #
    def create_mod_manager_tab(self):
        _create_mod_manager_tab(self)

#
# Entrypoint
#
if __name__ == '__main__':
    root = tkinter.Tk()
    app = BuoyUI(root)
    root.mainloop()