# TajsDesktop migration status

This fork is staged, not deployed. `src/scripts/cli.py` refuses live install
and uninstall while the configuration-preserving lifecycle remains unfinished.
Do not remove that guard merely because static tests or native builds pass.

## Identity work completed

- The GitHub fork is `tajemniktv/TajsDesktop`. Local `origin` points there;
  the original repository is retained as fetch-only `upstream`.
- Project-owned theme, plasmoid, executable, service, state, icon, cursor,
  wallpaper, and Acrylic Glass effect identifiers have been namespaced for
  the fork. Bundled icon and cursor archives were repacked with matching
  internal theme directory names.
- Release checks target the fork. The installer never auto-pulls or re-execs
  unreviewed code.
- The automatic upstream `kconf_update` step and stock-applet rewrite have
  been removed from the installation path. Those migrations must not be
  repurposed to overwrite existing upstream or stock KDE applet instances.
- Firefox uses distinct ownership markers and skips profiles containing an
  upstream managed block or shared `chrome` symlink instead of converting or
  replacing them automatically.
- Feature choices now save under the invoking user's config home, leaving the
  repository's `features.json` baseline untouched. `./install --plan` and the
  GUI provide a read-only installed-versus-requested delta. The GUI disables
  live install/uninstall while staging is active.
- `profiles/common.json` and the explicitly selectable
  `profiles/local-laptop.json` contain a reviewed, portable subset of this
  desktop's Dolphin, Konsole, Kate, MIME, workspace, shortcut, input, and
  power choices. `personal_defaults.preview_missing()` reports only absent
  user keys; even an explicit empty value remains user-owned. These profiles
  are **not applied yet**. No browser database, hardware identifier, home
  path, secret, or session value is copied into them.
- Feature previews classify detected upstream Tahoe as
  `migration-required`, not a clean first install. Panel Colorizer has a
  shared external ID, so the layout step now preserves any installed copy
  rather than replacing or shadowing it with the bundled version.
- KDE portal routing now creates only an absent file and records TajsDesktop
  ownership. Uninstall removes it only while both the ownership marker and
  original content match; user-edited or foreign routing remains untouched.

## Configuration-write audit in progress

| Area | Existing behavior requiring lifecycle work |
| --- | --- |
| Appearance | `apply`, `theme_switch`, `window_decorations`, `kvantum`, `sounds`, and `gtk` write live KDE/GSettings choices. Updates must install assets without invoking these selectors. |
| Panels and wallpapers | `layout` rebuilds panels and `apply` can reset wallpapers. Neither is safe as a routine update; explicit scoped reset needs a containment-level preview and backup. |
| App preferences | `nautilus` sets MIME handlers, bookmarks, overrides, and GSettings. Firefox has its own ownership-aware CSS path. App defaults need per-key absence and ownership checks. |
| Shared/system integration | Rounded Corners and Panel Colorizer use shared IDs; Plymouth touches boot configuration; OLED/theme schedulers manage user services or cron. Foreign ownership must be preserved. |
| Portal routing | The `portals` step previously overwrote its config and deleted it on uninstall. It now preserves foreign and edited files, but the rest of the broad installer is still blocked. |

## Remaining release gates

1. Replace the old all-in-one install/uninstall flow with first-install,
   asset-update, feature-reconciliation, and explicit scoped reset operations.
   A no-op feature change must not call the theme switcher or rebuild panels.
2. Audit every config-writing step, including KWin, look-and-feel, Kvantum,
   GTK, Firefox, Nautilus, Plymouth, portals, theme scheduling, and OLED care.
   Store versioned per-user ownership state; apply defaults only where KDE or
   the app has verified override semantics, otherwise initialize absent keys.
3. Treat existing Tahoe state as foreign by default. Offer an explicit,
   previewable migration with backups; never reinterpret Tahoe's state marker
   or panel IDs as TajsDesktop ownership. External KDE Rounded Corners is a
   shared dependency and must not be removed or reset if another installation
   owns it.
4. Make layout creation non-destructive on an existing desktop and preserve
   applet instances, panel geometry, pins, and wallpaper overrides. A reset
   must show exactly which keys or containments it will change and support
   rollback.
5. Persist versioned *installed* state only after each successful operation
   and make the preview executable through safe per-feature reconciliation.
   Add explicit, scoped reset actions to the GUI and CLI.
6. Complete the selective import and wire it to guarded first-install/reset
   only. Theme, Firefox, and Nautilus settings still need key-by-key review;
   native GSettings and application-specific ownership must not be inferred
   from a KConfig file. Preserve user edits on all later updates.
7. Reconcile remaining shared names, branding, and packaged paths; verify
   Qt/KWin builds and relevant systemd/OpenRC paths. Run the full test suite
   and a disposable KDE VM migration/rollback before allowing live use.

The Python suite and offline host builds of Acrylic Glass, Global Menu, and
Dock Task Manager pass; these do **not** verify a live Plasma session. The
existing user-modified `features.json` is intentionally not part of the fork
commits. No KDE settings, running desktop services, or installed files were
changed while preparing this branch.
