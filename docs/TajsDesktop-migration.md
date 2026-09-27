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
- The remaining Tahoe `kdedefaults` scrub call was removed from the fork's
  uninstall path. Global Menu's Plasma startup hook now has a fork-owned
  filename, so a later install or uninstall cannot replace Tahoe's hook.
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
  user keys; even an explicit empty value remains user-owned. An isolated
  first-install engine now backs up touched files and records each applied
  key before a confirmed reset may delete it; both operations preserve later
  overrides. They are **not wired into live installation yet**. `./install
  --plan --profile=local-laptop` and `--plan-reset-profile` are read-only.
  No browser database, hardware identifier, home path, secret, or session
  value is copied into the committed profiles.
- Feature previews classify detected upstream Tahoe as
  `migration-required`, not a clean first install. Panel Colorizer has a
  shared external ID, so the layout step now preserves any installed copy
  rather than replacing or shadowing it with the bundled version.
- KDE portal routing now creates only an absent file and records TajsDesktop
  ownership. Uninstall removes it only while both the ownership marker and
  original content match; user-edited or foreign routing remains untouched.
- GTK uninstall now removes only the fork-namespaced theme asset trees. It no
  longer deletes `~/.config/gtk-4.0` files or resets untracked GSettings that
  may belong to the user or another theme.
- Nautilus initialization now preserves existing MIME handlers, GTK bookmarks,
  CSS, and explicit dconf preferences. New bookmarks and CSS carry hash-bound
  fork ownership markers and are removed only if unchanged. The upstream
  `bookmarks.mac-tahoe-backup` is foreign state and is never consumed. MIME
  associations remain untouched on uninstall because the old path recorded
  no pre-install value; explicit reset still needs a scoped ownership record.
- The update planner now separates asset refresh from settings-only features.
  Asset-only phases exist for the bundled visual packages and compiled Global
  Menu, Dock Task Manager, Kvantum, and Acrylic payloads; an update preview
  lists unsupported refreshes instead of silently replaying install actions.
  The mandatory theme-switch executable and scheduler are listed as pending
  until an ownership-aware asset refresh is implemented; they cannot be
  hidden merely because they are absent from `features.json`.
  Wallpaper discovery now matches the fork-namespaced bundles. Cursor updates
  validate and stage the bundled archive before replacing either installed
  theme, so a broken archive leaves the current cursors intact.
- Layout first install adds fork panels without deleting existing KDE/Tahoe
  panels. Repeat install preserves them. Newly created panels carry a
  containment ownership key and a versioned snapshot of their Plasma
  containment and view configuration. Layout disable refuses legacy or
  modified panels; for unchanged fork-owned panels it backs up both Plasma
  configuration files, removes only the recorded panel IDs through Plasma's
  scripting API, and checks that removal persisted. The theme switcher no
  longer reapplies panel transparency to every user panel.
- Theme-switch removal now leaves legacy Tahoe-named executables and units,
  the layout ownership snapshot, and live `kdeglobals` preference keys alone.
  Only the fork's scheduler, executable, and wallpaper tracking state are
  retired. The old unowned cleanup path is not a safe migration mechanism.

## Configuration-write audit in progress

| Area | Existing behavior requiring lifecycle work |
| --- | --- |
| Appearance | `apply`, `theme_switch`, `window_decorations`, `kvantum`, `sounds`, and GTK install write live KDE/GSettings choices. Updates must install assets without invoking these selectors. GTK uninstall no longer deletes unrelated GTK4 files or resets GSettings. |
| Panels and wallpapers | Layout creation and removal are now scoped to newly marked, unchanged fork panels. A user-modified panel is preserved, not silently reset. `apply` can still reset appearance and wallpapers; it must not run on routine update. Explicit scoped panel reset with preview and rollback remains unfinished. |
| App preferences | Nautilus now initializes only absent MIME/bookmark/CSS/dconf values and preserves edits on uninstall; MIME rollback remains unimplemented without an ownership snapshot. Firefox has its own ownership-aware CSS path. Other app defaults need per-key absence and ownership checks. |
| Shared/system integration | Rounded Corners and Panel Colorizer use shared IDs; Plymouth touches boot configuration; OLED/theme schedulers manage user services or cron. Theme-switch uninstall now avoids legacy names and user preference keys, but service and cron ownership still need complete auditing. |
| Portal routing | The `portals` step previously overwrote its config and deleted it on uninstall. It now preserves foreign and edited files, but the rest of the broad installer is still blocked. |

## Remaining release gates

1. Replace the old all-in-one install/uninstall flow with first-install,
   asset-update, feature-reconciliation, and explicit scoped reset operations.
   The asset refresh phases are not yet dispatched by the CLI. A no-op feature
   change must not call the theme switcher or rebuild panels.
2. Audit every config-writing step, including KWin, look-and-feel, Kvantum,
   GTK, Firefox, Nautilus, Plymouth, portals, theme scheduling, and OLED care.
   Store versioned per-user ownership state; apply defaults only where KDE or
   the app has verified override semantics, otherwise initialize absent keys.
3. Treat existing Tahoe state as foreign by default. Offer an explicit,
   previewable migration with backups; never reinterpret Tahoe's state marker
   or panel IDs as TajsDesktop ownership. External KDE Rounded Corners is a
   shared dependency and must not be removed or reset if another installation
   owns it.
4. Finish layout lifecycle: expose a preview and confirmed scoped reset for
   modified fork panels, preserve user pins and geometry, and verify backup
   restoration in an isolated KDE VM. Keep unproven legacy panels foreign.
5. Persist versioned *installed* state only after each successful operation
   and make the preview executable through safe per-feature reconciliation.
   Add explicit, scoped reset actions to the GUI and CLI.
6. Wire the reviewed profile engine to guarded first-install and explicit
   reset only, then expose local-machine selection and reset confirmation in
   the GUI. Theme and Firefox defaults still need key-by-key review; native
   GSettings and application-specific ownership must not be inferred from a
   KConfig file. Preserve user edits on all later updates.
7. Reconcile remaining shared names, branding, and packaged paths; verify
   Qt/KWin builds and relevant systemd/OpenRC paths. Run the full test suite
   and a disposable KDE VM migration/rollback before allowing live use.

The Python suite and offline host builds of Acrylic Glass, Global Menu, and
Dock Task Manager pass; these do **not** verify a live Plasma session. The
existing user-modified `features.json` is intentionally not part of the fork
commits. No KDE settings, running desktop services, or installed files were
changed while preparing this branch.
