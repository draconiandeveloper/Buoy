# How to Use HLS: Reborn on Linux and Steam Deck

This process has **not been tested by me**. The tests and screenshots are from **@dandestroys** on Discord. Huge thanks to them for their efforts!

---

## Steps 1-6
<div align="center">
  <img src="https://github.com/FerretPaws/HLSReborn/blob/main/repores/LinuxUsageSteps1-6.png?raw=true" alt="HLSR Icon" />
</div>

1. Select Add Game from your Steam Library .
2. Choose Add a Non-Steam Game.
3. Click Browse
4. Navigate to where you downloaded and extracted HLS: Reborn
5. Click the **`HookLineSinkerReborn.exe`** and press Select (Or whatever is similar in your explorer) 
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

### Tips
- If you encounter any issues, visit the [Repository](https://github.com/FerretPaws/HLSReborn) or ask in the **Discord** for help!

