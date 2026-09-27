#!/bin/sh
# kconf_update helper: rewrite old dock applet IDs to the MacTahoe dock fork
# in plasma-org.kde.plasma.desktop-appletsrc. KF6 kconf_update runs scripts
# with no arguments, so argless it targets the live file; the installer and
# tests pass an explicit file instead. Mirrors plasmoids._APPLETSRC_RENAMES.

f=${1:-"${XDG_CONFIG_HOME:-$HOME/.config}/plasma-org.kde.plasma.desktop-appletsrc"}
[ -f "$f" ] || exit 0

# A separately installable fork must never rewrite stock or upstream Tahoe
# applet instances. There are no older TajsDesktop applet IDs to migrate.
exit 0
