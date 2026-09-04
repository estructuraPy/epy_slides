# Roadmap

Direction of record for `epy_slides`, kept beside `CHANGELOG.md`: this file
records what the application is expected to become, the changelog records
what it already is.

Author of record: Ing. Angel Navarro-Mora M.Sc.

## The document family

`epy_slides` produces slide decks. It is one of the editors `epy_studio` hosts,
alongside `epy_reports` and `epy_papers` and `epy_draft`, and they share the export
engines in `epy_export`. Anything recorded here that names the family
applies to the siblings too, and is recorded in their roadmaps as well.

## Shipped

### Optional autosave (2026-09-01, shipped 835e394 on 2026-09-02)

The editor offers an autosave the user can turn on or off. Both things
this had to get right are pinned by tests, each with a planted defect
that fails it:

- **Opt-in, and it stays where the user left it.** A checkable
  *Autosave* action in the View menu, off on a fresh install, persisted
  under the `autosave` settings key. An editor that starts saving on its
  own is an editor that overwrote a draft somebody was still deciding
  about.
- **A save never lands on top of an export.** Every export raises a
  counter on the window and lowers it in a `finally` -- including the
  error paths and the nested event loops of a progress dialog -- and the
  timer does nothing while it is up. A counter stuck at one would
  silently disable autosave for the session, which is why the failing
  path is a test of its own.

The two questions left open when this was written, answered by what was
built: a deck that has never been saved is **skipped**, because
`tab.save()` returns False without a path and routing through the manual
save would raise a modal Save As dialog on somebody mid-sentence; and
the interval is **fixed** (`AUTOSAVE_INTERVAL_MS`, 30 s), because the
preference that matters is on/off and a second knob buys nothing. The
write goes through `epy_export.write_text_atomic`, so a save that dies
mid-write cannot truncate the only copy.

Found and fixed alongside it: the PDF export did not stop the live
preview debounce first, so a pending re-render could load the preview
deck into the same view the export was printing from and `printToPdf`
failed without writing a file. `epy_reports` had stopped it since the
day that was diagnosed there; this one had not.

## Pending

Nothing scheduled.
