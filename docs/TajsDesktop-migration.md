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
6. Selectively import portable settings for KDE workspace, shortcuts, input,
   power, window behavior, theme, default applications, Dolphin, Konsole,
   Kate, Firefox, and Nautilus into common defaults plus one named local
   profile. Review each imported key; exclude credentials, browser databases,
   caches, session state, and machine identifiers.
7. Reconcile remaining shared names, branding, and packaged paths; verify
   Qt/KWin builds and relevant systemd/OpenRC paths. Run the full test suite
   and a disposable KDE VM migration/rollback before allowing live use.

The Python suite and offline host builds of Acrylic Glass, Global Menu, and
Dock Task Manager pass; these do **not** verify a live Plasma session. The
existing user-modified `features.json` is intentionally not part of the fork
commits. No KDE settings, running desktop services, or installed files were
changed while preparing this branch.
