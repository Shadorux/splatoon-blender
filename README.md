Splatoon Tools 2.0.1 - Blender 5.2 compatibility build

MAINTAINER / DISCLAIMER
This maintained update is by Shadorux. The original project is Coconuts XXS'
Blender-Splatoon-Tool: https://github.com/CoconutsXXS/Blender-Splatoon-Tool
This repository updates and maintains that original work; it is not the
original author's repository.

INSTALL
1. Remove or disable older Splatoon Tools copies.
2. In Blender, open Edit > Preferences > Add-ons.
3. Choose Install from Disk and select the supplied ZIP without extracting it.
4. Enable Splatoon Tools.

USE
- Create a character: Shift+A > Mesh > Inkling.
- Open the 3D View sidebar with N and choose the Splatoon tab for persistent
  character customization. The panel remains available after the F9 popup
  closes.
- Select the Inkling armature before importing clothes or shoes.
- Import gear: File > Import > Splatoon Cloth (.fbx).
- Set Cloth Type to Body Cloth, Shoes, or Head Accessory as appropriate.
- Import weapons: File > Import > Splatoon Weapon (.fbx).

MODEL FILES
- Keep each FBX beside its PNG texture files.
- Blender 5.2 cannot import Collada .dae files. Convert those models to FB

NOTABLE FIXES
- Blender 5.2-safe module registration and package-relative asset paths.
- Modern Principled BSDF shader sockets and reliable image loading.
- Context-safe selection, object-mode handling, and import cleanup.
- Correct Blender 5.2 scaling for characters, clothing, items, and weapons.
- Stable cloth cleanup that avoids the native dependency-graph crash.
- Correct shoe mirroring and Inkling-armature placement
