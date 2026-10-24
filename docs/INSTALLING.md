# Using an existing local installer package

This public repository excludes Apple firmware, signing tickets, the androidi4 userspace package, N1 firmware, and calibration. Complete 02.4 packages come from the locally verified build and enforce device identity and input checks. They are not universal installers for arbitrary devices.

## Import

```bash
python3 tools/import-installer.py /path/to/T4-Android-Installer-02.4.zip
```

The importer checks ZIP paths, the file manifest, sizes, and SHA-256 hashes, then stores the package in `saved/packages/T4-Android-Installer-02`. It does not connect to the device.

## Run

Use the existing Kit to enter an SSH ramdisk. Keep SSH forwarding active and the system volume mounted. The current workflow uses port 6414; the port and Kit path can be configured in the menu. This tool does not reinstall iOS.

```bash
bash start.sh
```

Run the check action first to inspect the detected device and version. To install, select the installation action and confirm the displayed version. The entry point stores session state in `saved/state/installer02/`. Existing installer prompts remain in their original language.

Individual actions are also available:

```bash
bash start.sh verify
bash start.sh check --port 6414 --kit "$HOME/Legacy-iOS-Kit"
bash start.sh install --port 6414 --kit "$HOME/Legacy-iOS-Kit"
```

## Confirm each result separately

1. `COMPLETE_IMAGE_SET_API_ACCEPTED` means only that the update interface accepted the images.
2. OpeniBoot `0525:1280` and the expected `version` reply establish that OpeniBoot is running.
3. Observe the displayed menu and selection movement.
4. Confirm iOS, Android, touch, and buttons individually.
5. Confirm the menu and operating systems after rebooting with USB disconnected before recording independent boot as successful.

Keep the logs and ramdisk available after an interrupted firmware submission, an unknown result, or a failed cold boot. The installer handles legacy RAM locks separately; deleting a lock alone is not grounds to repeat a submission. Existing package audit paths are not automatically migrated. When copying earlier records, retain their referenced backups too.
