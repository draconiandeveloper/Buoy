import aiofiles
import asyncio
import zipfile
import yaml
import json
import sys
import os
import io

class FileIO:
    def __init__(self, filename, mode='r'):
        self.appdata = os.getenv('APPDATA') if sys.platform == 'win32' else \
            os.path.join(os.getenv('HOME'), '.local', 'share')

        self.filename = filename
        self.mode = mode
    
    def get_godot_path(self):
        return os.path.join(self.appdata, 'Godot') if sys.platform == 'win32' else \
            os.path.join(
                self.appdata,
                'Steam',
                'steamapps',
                'compatdata',
                '3146520',
                'pfx',
                'drive_c',
                'users',
                'steamuser',
                'AppData',
                'Roaming',
                'Godot'
            )
    
    def get_temp_path():
        return os.path.join(self.appdata, 'Hook_Line_Sinker_Reborn', 'temp')

    #
    # Zip archive functions
    #
    
    async def _extract_zip(self, destination):
        _zipdata = b''

        if not os.path.isfile(self.filename):
            return
        
        if not zipfile.is_zipfile(self.filename):
            return

        async with aiofiles.open(self.filename, 'rb') as _zipfile:
            _zipdata = await _zipfile.read()
        
        async with zipfile.ZipFile(io.BytesIO(_zipdata)) as _zipfile:
            for entry in _zipfile.infolist():
                xpath = os.path.join(destination, entry.filename)

                if not entry.is_dir():
                    async with aiofiles.open(xpath, 'wb') as _file:
                        await _file.write(_zipfile.read(entry))
                else:
                    os.makedirs(xpath, exist_ok=True)
    
    def extract_zip(self, destination):
        asyncio.run(self._extract_zip(destination))
    
    #
    # YAML functions
    #

    async def _read_yaml_data(self):
        yamldata = ''

        async with aiofiles.open(self.filename, 'r') as _yamlfile:
            yamldata = await _yamlfile.read()
        
        return yamldata

    def parse_yaml_theme(self):
        yamldata = asyncio.run(self._read_yaml_data())
        _parsed = yaml.safe_load(yamldata)

        parsed = {}
        for k, v in _parsed['elements'].items():
            parsed.update({'bg' if k == 'body' else f'{k}_bg': f'#{v['bg']}'})
            parsed.update({'fg' if k == 'body' else f'{k}_fg': f'#{v['fg']}'})
        
        return parsed
    
    #
    # JSON functions
    #

    async def _load_json_data(self):
        jsondata = ''

        async with aiofiles.open(self.filename, 'r') as _jsonfile:
            jsondata = await _jsonfile.read()
        
        return jsondata
    
    def parse_json_file(self):
        jsondata = asyncio.run(self._load_json_data())
        return json.loads(jsondata)