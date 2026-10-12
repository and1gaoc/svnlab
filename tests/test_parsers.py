from svnlab.parsers import parse_info_xml, parse_log_xml, parse_svn_diff


def test_parse_info_and_verbose_log() -> None:
    info = parse_info_xml(
        """<?xml version="1.0"?>
        <info><entry kind="dir" path="." revision="42"><url>https://svn.example/repo</url>
        <repository><root>https://svn.example/repo</root><uuid>abc</uuid></repository></entry></info>"""
    )
    assert info == {
        "revision": 42,
        "kind": "dir",
        "url": "https://svn.example/repo",
        "repository_root": "https://svn.example/repo",
        "repository_uuid": "abc",
    }

    commits = parse_log_xml(
        """<?xml version="1.0"?><log><logentry revision="42"><author>lin</author>
        <date>2026-10-12T08:30:00.000000Z</date><paths>
        <path action="M" kind="file">/trunk/app.py</path>
        <path action="A" copyfrom-path="/trunk/old.py" copyfrom-rev="40">/trunk/new.py</path>
        </paths><msg>Fix parser</msg></logentry></log>"""
    )
    assert commits[0].revision == 42
    assert commits[0].changed_file_count == 2
    assert commits[0].changed_paths[1].copy_from_revision == 40


def test_parse_multifile_text_binary_and_property_diff() -> None:
    payload = """Index: src/app.py
===================================================================
--- src/app.py\t(revision 4)
+++ src/app.py\t(revision 5)
@@ -1,3 +1,4 @@
 def run():
-    return 1
+    value = 2
+    return value
 
Index: assets/logo.png
===================================================================
Cannot display: file marked as a binary type.
svn:mime-type = application/octet-stream
Index: README.md
===================================================================
--- README.md\t(revision 4)
+++ README.md\t(revision 5)
Property changes on: README.md
___________________________________________________________________
Modified: svn:eol-style
## -1 +1 ##
-native
+LF
"""
    files = parse_svn_diff(payload)
    assert [item.path for item in files] == ["src/app.py", "assets/logo.png", "README.md"]
    assert files[0].hunks[0].lines[1].kind == "deletion"
    assert files[0].hunks[0].lines[2].new_line == 2
    assert files[1].binary is True
    assert files[1].status == "binary"
    assert files[2].status == "property"
    assert "Modified: svn:eol-style" in files[2].property_changes


def test_parse_added_and_deleted_status() -> None:
    payload = """Index: new.txt
===================================================================
--- new.txt\t(nonexistent)
+++ new.txt\t(revision 3)
@@ -0,0 +1 @@
+new
Index: old.txt
===================================================================
--- old.txt\t(revision 2)
+++ old.txt\t(nonexistent)
@@ -1 +0,0 @@
-old
"""
    files = parse_svn_diff(payload)
    assert files[0].status == "added"
    assert files[1].status == "deleted"

