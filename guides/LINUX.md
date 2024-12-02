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
