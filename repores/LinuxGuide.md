# How to Use Buoy on Linux and Steam Deck

## Buoy cannot be easily compiled directly on Linux but it can be run through Proton with some set-up shown below from the latest pre-compiled exe in Releases

This process has **not been tested by me**. The tests and screenshots are from **@dandestroys** on Discord. Huge thanks to them for their efforts!

This guide was written for HLS: Reborn and has not been adapted for the rebrand, it all applies the same and all directotry files are the same as before so this guide is still fully working and valid.

---

## Steps 1-6
<div align="center">
  <img src="https://github.com/FerretPaws/HLSReborn/blob/main/repores/LinuxUsageSteps1-6.png?raw=true" alt="HLSR Icon" />
</div>

1. Select Add Game from your Steam Library .
2. Choose Add a Non-Steam Game.
3. Click Browse
4. Navigate to where you downloaded and extracted HLS: Reborn
5. Click the **`HookLineSinkerReborn.exe`** (Now **Buoy v#.exe**) and press Select (Or whatever is similar in your explorer) 
6. Click Add Selected Programs

---

## Steps 7-12
<div align="center">
  <img src="https://github.com/FerretPaws/HLSReborn/blob/main/repores/LinuxUsageSteps7-12.png?raw=true" alt="Steps 7-12" />
</div>

7. Choose "HookLineAndSinkerReborn" from your Steam Library 
8. Click the cogwheel icon
9. Click the Properties option 
10. Go to Compatibility 
11. Ensure that **`Force the use of a specific Steam Play compatibility tool`** is checked. Choose any Proton version **`between 7 and 9`** from the list (Or install any you need if you don't have them)
12. Run HLS: Reborn

---

## Steps 13-22
<div align="center">
  <img src="https://github.com/FerretPaws/HLSReborn/blob/main/repores/LinuxUsageSteps13-22.png?raw=true" alt="Steps 13-19" />
</div>

13. Go to the HLS: Reborn Setup tab
14. Go to Steam and choose to Browse local files
15. Copy the path to the directory that holds your WEBFISHING data
16. Choose Browse in HLS: Reborn Setup tab
17. Paste the path to your game directory into the File Path input
18. Ensure that's the correct path and choose Open
19. Go to WEBFISHING's Properties menu
20. In the Launch Options section, copy and paste this **`WINEDLOVERRIDES=“winmm.dll=n,b” %command%`**
21. Click into the Compatibility tab and change the Proton version to **`Proton Experimental`**
22. Go back to the HLS: Reborn Setup tab and choose to Install GDWeave.
23. You're done! (Hopefully!!)

---

## To get the Save Manager working, follow this guide:

Follow these steps to configure the save manager to work with your setup:

1. **Navigate to the target directory:**  
   Locate the directory where Steam stores its compatdata. Use the following path, replacing `[HSLR_STEAM_ID]` with your app's unique Steam ID (note: Steam auto-generates these IDs for non-Steam games, so they will differ for each installation):  
   ```~/.local/share/Steam/steamapps/compatdata/[HSLR_STEAM_ID]/pfx/drive_c/users/steamuser/AppData/Roaming```

2. **Determine the Godot directory location:**  
   Find the Godot folder in the following path:  
   ```~/.local/share/Steam/steamapps/compatdata/3146520/pfx/drive_c/users/steamuser/AppData/Roaming```

3. **Create a symbolic link:**  
   Symlink the Godot folder from the path above (3146520) to the directory corresponding to your app's `[HSLR_STEAM_ID]`. Use the following command, replacing `[HSLR_STEAM_ID]` as needed:  
   ```ln -s ~/.local/share/Steam/steamapps/compatdata/3146520/pfx/drive_c/users/steamuser/AppData/Roaming/Godot```
         ```~/.local/share/Steam/steamapps/compatdata/[HSLR_STEAM_ID]/pfx/drive_c/users/steamuser/AppData/Roaming/Godot```

4. **Verify the symlink:**  
   Confirm that the symlink was created successfully by navigating to the `[HSLR_STEAM_ID]` directory:  
   ```cd ~/.local/share/Steam/steamapps/compatdata/[HSLR_STEAM_ID]/pfx/drive_c/users/steamuser/AppData/Roaming```
   Use ls -l to verify the Godot link points to the correct location.

5. **Flatpak users:**  
   If you are using Steam via Flatpak, note that the directory structure will differ. The equivalent path for Flatpak installations is typically:  
   ```~/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/compatdata/```

Once the symlink is correctly established, the save manager should function as expected. 🎉


### Tips
- If you encounter any issues, visit the [Repository](https://github.com/FerretPaws/HLSReborn) or ask in the **Discord** for help!

