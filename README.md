# **Buoy**  

**Buoy** is a **mod manager** designed for **WEBFISHING** using **GDWeave**!

<div align="center">
  <img src="https://github.com/FerretPaws/Buoy/blob/main/repores/BuoyIcon.png?raw=true" alt="HLSR Icon" />
</div>

---

## **Features**  
- 🎯 **Easy mod installation and management**  
- 🔄 **Automatic updates** for mods and the GDWeave mod loader  
- 🛠️ **User-friendly interface** for enabling/disabling mods  
- ⚙️ **Mod configuration editing**  
- 📦 **Import custom mods** from ZIP files
- 🔍 **Search functionality** for available and installed mods  
- 📝 **Detailed mod information display**  
- ⚡ **One-click setup** for game directory and required components  
- 🚫 **NO MORE USER TRACKING!!**  

---

## **Using Buoy**  

If you're coming from **HLS**, there is a tool for **importing your old mods and settings** to this version.  

1. Download the **BuoyImporter.exe** from the [latest release](https://github.com/FerretPaws/Buoy/releases) tab.  
2. Run it **before launching Buoy for the first time**—your data will be transferred.  
3. You can delete the **BuoyImporter.exe** after the process is complete.  

**To install Buoy:**  
- Download the [latest release ZIP](https://github.com/FerretPaws/Buoy/releases), extract the .zip to anywhere you like, then run the .exe inside there. Simple as that! Just remember to keep it inside the folder it extracts from!
- You’ll need to go through a one-time setup process.  

⚠️ **Do NOT download the source code** unless you know what you’re doing.  

## **Building on Linux**

1. Open the project's root directory *(the one that contains this Markdown file)*.

2. Run: `python -m venv venv`.

3. Access the virtual Python environment: `source venv/bin/activate`.

    - If you're using FISH as your shell, then `source venv/bin/activate.fish`.

    - If you're using CSH as your shell, then `source venv/bin/activate.csh`.

4. Install requirements: `pip install -r requirements.txt`

5. Build: `python compiler.py`

## **USING HLSR ON LINUX OR STEAM DECK**

### Installing .NET 8 with WINE/Proton

**This process requires you to install winetricks on your system**, you can likely find winetricks for your distribution as follows:
    
- Debian/Ubuntu/Mint: `apt-cache search winetricks`

- Arch/EndeavourOS/CachyOS: `pacman -Ss winetricks`

- OpenSUSE: `zypper search winetricks`

- Gentoo: `emerge --search winetricks`

- Fedora/RedHat/RHEL: `dnf search winetricks`

- Void: `xbps-query -Rs winetricks`

- Alpine: `apk search winetricks`

From there you'll have to install the winetricks program:

- Debian/Ubuntu/Mint: `apt-get install {winetricks package name}`

- Arch/EndeavourOS/CachyOS: `pacman -S {winetricks package name}`

- OpenSUSE: `zypper install {winetricks package name}`

- Fedora/RedHat/RHEL: `dnf install {winetricks package name}`

- Void: `xbps-install -S {winetricks package name}`

- Alpine: `apk add {winetricks package name}`

Then you'll run the following in a terminal: `WINEPREFIX=$HOME/.local/share/Steam/steamapps/compatdata/3146520/pfx winetricks dotnet8`

From there you'll run through the installation process as you normally would under Windows.

### Launching Webfishing with GDWeave

- Open Steam and go to the Library tab to see your games.

- Right-click on WEBFISHING and select Properties.

- In the General tab, add the following to Launch Options: `WINEDLLOVERRIDES="winmm=n,b" %command%`

- Close out of the Properties window and you're ready to go fishing!

### Old Resource

- Follow the guide **[here](https://github.com/FerretPaws/Buoy/blob/main/repores/LinuxGuide.md)**

---

## **Troubleshooting / Tips**  

- ❗ If you encounter any issues, try running the program as **administrator**.  
- ⚙️ You may need to install **[.NET 8](https://dotnet.microsoft.com/en-us/download/dotnet/8.0)** manually. While the installer attempts to automate this, it's not perfect.
- ⚙️ If the game runs without mods when you chose the modded run option, run WEBFISHING through Steam first and then go back to HLS:R and relaunch through there. (This is an uncommon issue)
