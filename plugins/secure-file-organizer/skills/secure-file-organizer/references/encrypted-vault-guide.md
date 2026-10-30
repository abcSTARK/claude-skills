# Encrypted Volume Guide (macOS)

Personal reference for creating and maintaining encrypted disk images (sparsebundles) on macOS, used to store sensitive personal documents (IDs, financial records, credentials) outside of plain unencrypted folders.

## Where it lives

The volume is a package folder, e.g. `~/Documents/Personal_Secure.sparsebundle` — not a single file. Finder shows it as one disk-image icon, but internally it's `Info.plist`, `token`, and a `bands/` directory holding the encrypted data in chunks. Don't open or edit its internals directly — only interact with it via mount/unmount.

**Don't delete it.** The sparsebundle folder *is* the permanent encrypted data. The mount point under `/Volumes/...` is just a temporary unlocked view — deleting things there deletes the real data, but deleting the mount point itself does nothing (it disappears on eject anyway). The only way to actually lose the vault is deleting the `.sparsebundle` folder from its real location (e.g. emptying Trash after dragging it there), or losing the password with no backup.

## Create a new encrypted volume

```bash
hdiutil create -size 4g -fs APFS -encryption AES-256 -volname "MyVault" -type SPARSEBUNDLE ~/Documents/MyVault
```

- `-size 4g` — ceiling, not pre-allocated. The file only grows as data is added.
- `-type SPARSEBUNDLE` — grows as needed, resizable later. (`SPARSE` = single-file growable image; omit `-type` for a fixed-size `.dmg` that pre-allocates immediately.)
- `-fs APFS` — modern filesystem, native encryption support, resizes cleanly.
- `-encryption AES-256` — triggers the password-setup dialog (set via a native macOS prompt, never typed into a terminal/chat).
- Auto-mounts after creation.

## Mount (unlock)

```bash
hdiutil attach ~/Documents/MyVault.sparsebundle
```
Or double-click the `.sparsebundle` in Finder and enter the password. Mounts at `/Volumes/MyVault`.

## Eject (lock)

```bash
hdiutil detach /Volumes/MyVault
```
Or click the eject icon next to it in Finder's sidebar. Always eject when done — don't leave it mounted longer than needed, since anything with disk access on the Mac can read it while unlocked.

Use `-force` only if it's stuck (e.g. a Finder window still browsing it):
```bash
hdiutil detach -force /Volumes/MyVault
```

## Adding / modifying documents

1. Mount it.
2. Drag files in, edit them, organize subfolders — all writes go straight to the underlying sparsebundle in real time (same as any mounted drive, not a cache).
3. Delete the original unencrypted copy from wherever it was sitting (Downloads, Desktop, etc.) — otherwise you've just made a second copy instead of securing the first.
4. Eject.

Ejecting does not discard anything — it flushes pending writes and re-locks. Whatever was on the volume when you ejected is exactly what's there next time you mount it.

## Verify it's actually encrypted

```bash
hdiutil info | grep -A5 MyVault.sparsebundle | grep image-encrypted
```
Should print `image-encrypted : TRUE`.

**Gotcha:** `diskutil info /Volumes/MyVault` while mounted will say `Encrypted: No` — that's expected, it describes the already-decrypted live view, not the disk image's own encryption. Use `hdiutil info` (above) for the real answer.

## Resize later

```bash
hdiutil resize -size 10g ~/Documents/MyVault.sparsebundle
```
(Must be unmounted first.)

## Change the password

```bash
hdiutil chpass ~/Documents/MyVault.sparsebundle
```
Prompts for old password, then new one, via a native dialog.

## GUI alternative (no Terminal)

Disk Utility → File → New Image → Blank Image (or Image from Folder) → Encryption: 256-bit AES → Image Format: sparse bundle disk image.
