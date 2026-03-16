# Quick Reference - Test Commands

## Run All Tests Sequentially (Recommended)
```bash
./run_tests_sequentially.sh
```

## Individual Endpoint Commands

### 1. Clip Reel Sharing
```bash
pytest tracevision/tests/test_clip_reel_sharing.py::TestClipReelSharing -v
```

### 2. Shared By Me
```bash
pytest tracevision/tests/test_clip_reel_sharing.py::TestListSharedReels -v
```

### 3. Clip Reel Comments
```bash
pytest tracevision/tests/test_clip_reel_comments.py::TestClipReelComments -v
```

### 4. Comment Likes
```bash
pytest tracevision/tests/test_clip_reel_comments.py::TestCommentLikes -v
```

### 5. Highlight Notes (Create)
```bash
pytest tracevision/tests/test_highlight_notes_mocked.py::TestHighlightNotesCreateMocked -v
```

### 6. Highlight Notes (List)
```bash
pytest tracevision/tests/test_highlight_notes_mocked.py::TestHighlightNotesListMocked -v
```

### 7. All Endpoints (Mocked - All Tests)
```bash
# Run each test class separately
pytest tracevision/tests/test_all_endpoints_mocked.py::TestClipReelShareMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestClipReelSharedByMeMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestClipReelCommentsCreateMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestClipReelCommentsListMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestClipReelListMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestHighlightNotesCreateMocked -v
pytest tracevision/tests/test_all_endpoints_mocked.py::TestHighlightNotesListMocked -v
```

## Run by Test File
```bash
pytest tracevision/tests/test_clip_reel_sharing.py -v
pytest tracevision/tests/test_clip_reel_comments.py -v
pytest tracevision/tests/test_highlight_notes_mocked.py -v
pytest tracevision/tests/test_all_endpoints_mocked.py -v
```

## Useful Options
- `-v` : Verbose output
- `-vv` : Very verbose output
- `-s` : Show print statements
- `--lf` : Run last failed tests only
- `--maxfail=1` : Stop after first failure
