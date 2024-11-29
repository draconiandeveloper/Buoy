# How to build on Linux

## Create Virtual Environment

1. Open the project's root directory *(the one that contains this Markdown file)*.

2. Run: `python -m venv venv`.

3. Access the virtual Python environment: `source venv/bin/activate`.

    - If you're using FISH as your shell, then `source venv/bin/activate.fish`.

    - If you're using CSH as your shell, then `source venv/bin/activate.csh`.

4. Install requirements: `pip install -r requirements.txt`

5. Build: `python compiler.py`

## Installing .NET 8 with WINE/Proton

**This process requires you to install winetricks on your system**, you can likely find winetricks for your distribution as follows:
    
- Debian/Ubuntu/Mint: `apt-cache search winetricks`

- Arch: `pacman -Ss winetricks`

- OpenSUSE: `zypper search winetricks`

- Gentoo: `emerge --search winetricks`

- Fedora/RedHat/RHEL: `dnf search winetricks`

- Void: `xbps-query -Rs winetricks`

- Alpine: `apk search winetricks`

Then you'll run the following in a terminal: `WINEPREFIX=$HOME/.local/share/Steam/steamapps/compatdata/3146520/pfx winetricks dotnet8`

From there you'll run through the installation process as you normally would under Windows.

## Launching Webfishing with GDWeave

- Open Steam and go to the Library tab to see your games.

- Right-click on WEBFISHING and select Properties.

- In the General tab, add the following to Launch Options: `WINEDLLOVERRIDES="winmm=n,b" %command%`

- Close out of the Properties window and you're ready to go fishing!

## Known Issues

- Extracting the GDWeave archive does not place `winmm.dll` in game installation path on Linux.