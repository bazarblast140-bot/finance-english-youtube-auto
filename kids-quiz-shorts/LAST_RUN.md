# Last run
- when   : 2026-08-29 04:25 UTC
- slot   : noon
- privacy: unlisted
- upload : failure

## metadata

## upload output (tail)
```
Traceback (most recent call last):
  File "/home/runner/work/finance-english-youtube-auto/finance-english-youtube-auto/kids-quiz-shorts/src/upload.py", line 214, in <module>
    upload(a.dir / "metadata.json", a.privacy, pub_at)
  File "/home/runner/work/finance-english-youtube-auto/finance-english-youtube-auto/kids-quiz-shorts/src/upload.py", line 115, in upload
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py", line 1058, in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py", line 1044, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'out/20260829_noon/metadata.json'

[upload] FAILED (http=None): [Errno 2] No such file or directory: 'out/20260829_noon/metadata.json'
```

## voice
```
```

## telegram
```
telegram: sent (http 200)
```
