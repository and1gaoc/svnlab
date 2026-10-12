# SVNLab Encoding and Split-Scroll Design

## Problem

SVNLab currently assumes every textual SVN response is UTF-8. That is safe for neither native-client diagnostics nor repository file bytes, and cached mojibake persists after the decoder is fixed. In split diff mode, each rendered row owns its own two-column grid, so a long line can overflow into the opposite pane instead of expanding a shared scrollable surface.

## Decisions

### Encoding

- Feed `svn info --xml` and `svn log --xml` output to the XML parser as bytes so the XML declaration controls decoding.
- Decode diff output, file content, and stderr through one helper. It recognizes UTF BOMs first, then strict UTF-8, the operating-system preferred encoding, and GB18030 before using a replacement fallback.
- Continue treating NUL-bearing file data as binary.
- Version persistent cache keys so values decoded by the former UTF-8-only path are not reused.

### Split diff layout

- Keep old and new panes in one fixed two-column CSS grid so both remain visible.
- Clip long code inside its own half and expose one scrollbar below the split table.
- Synchronize that scrollbar with every old/new code cell. Both panes therefore move by the same horizontal distance while their line-number columns remain fixed and neither side can paint over the other.
- Unified and source views retain their existing independent scrolling behavior.

## Verification

- Unit tests cover UTF-8 XML bytes, GB18030 diff/file text, BOM-aware Unicode, and cache versioning.
- Browser QA injects an intentionally long split-diff line, moves the shared scrollbar, and verifies both panes receive the same horizontal offset without overlap.
- Run lint, the full test suite, browser QA, and packaged-EXE smoke checks.

## Scope Boundaries

Automatic charset detection for arbitrary legacy encodings is not guaranteed. The supported fallback set targets UTF Unicode encodings and common Simplified-Chinese Windows repositories without adding a third-party detector.
