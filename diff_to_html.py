import sys
import html
import re

# Inline CSS for side-by-side diff
STYLE = '''
<style>
body { 
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    background: #0d1117; 
    color: #f0f6fc;
    margin: 0; 
    padding: 0; 
}
.container { display: flex; height: 100vh; }
.file-explorer { 
    width: 300px; 
    min-width: 150px;
    max-width: 600px;
    background: #161b22; 
    border-right: 1px solid #30363d; 
    overflow-y: auto;
    padding: 10px;
    box-sizing: border-box;
    transition: width 0.1s;
}
.resizer {
    width: 6px;
    cursor: ew-resize;
    background: #22262d;
    border-right: 1px solid #30363d;
    z-index: 10;
    position: relative;
}
.resizer:hover, .resizer.active {
    background: #1f6feb;
}
.file-explorer h2 { 
    margin-top: 0; 
    color: #f0f6fc; 
    font-size: 16px;
    font-weight: 600;
}
.file-item {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 4px;
    margin-bottom: 2px;
    transition: background-color 0.2s;
    color: #f0f6fc;
    /* Ensure no wrapping */
    white-space: nowrap;
}
.file-item:hover { background: #21262d; }
.file-item.selected { background: #1f6feb; color: #ffffff; }
.file-item.reviewed { background: #2d1f0a; }
.diff-view { 
    flex: 1; 
    overflow-y: auto; 
    padding: 20px;
    background: #0d1117;
}
.diff-section { display: none; }
.diff-section.active { display: block; }
.diff-section h2 {
    color: #f0f6fc;
    margin-bottom: 20px;
    font-size: 18px;
    font-weight: 600;
}
.diff-section h3 {
    color: #f0f6fc;
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 500;
}
table.diff { 
    border-collapse: collapse; 
    width: 100%; 
    table-layout: auto; 
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
}
td, th { 
    padding: 0.4em 0.8em; 
    vertical-align: top; 
    border-bottom: 1px solid #30363d;
}
tr.added { background: #0a2d0a; }
tr.removed { background: #2d0a0a; }
tr.unchanged { background: #161b22; }
tr.changed { background: #2d1f0a; }
tr.added:hover { background: #145c14; }
tr.removed:hover { background: #7a2323; }
tr.changed:hover { background: #7a5a23; }
tr.unchanged:hover { background: #21262d; }
td.lineno { 
    color: #7d8590; 
    width: 4em; 
    font-size: 12px;
    text-align: right;
    border-right: 1px solid #30363d;
    user-select: none;
    -webkit-user-select: none;
}
td.code { 
    white-space: pre; 
    word-wrap: break-word;
    width: calc(100% - 4em);
    color: #f0f6fc;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
}
th { 
    background: #21262d; 
    color: #f0f6fc;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.file-item-checkbox {
    margin-right: 8px;
    vertical-align: middle;
    accent-color: #1f6feb;
}
.folder-heading {
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 4px;
}
.folder-heading .folder-arrow {
    font-size: 12px;
    transition: transform 0.2s;
    width: 1em;
    display: inline-block;
    text-align: center;
}
.folder-heading.collapsed .folder-arrow {
    /* No rotation, just change character via JS */
}
.folder-contents {
    margin-left: 16px;
}
.folder-contents.collapsed {
    display: none;
}
.folder-checkbox {
    margin-right: 6px;
    vertical-align: middle;
    accent-color: #1f6feb;
    pointer-events: none;
}
</style>
<script>
function showFile(fileId) {
    // Hide all diff sections
    document.querySelectorAll('.diff-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Show selected file's diff
    const selectedSection = document.getElementById('diff-' + fileId);
    if (selectedSection) {
        selectedSection.classList.add('active');
    }
    
    // Update file explorer selection
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('selected');
    });
    document.querySelector('.file-item[data-file="' + fileId + '"]').classList.add('selected');
    
    // Set up scroll synchronization for the selected file
    setTimeout(syncScroll, 100);
}

function syncScroll() {
    const activeSection = document.querySelector('.diff-section.active');
    if (!activeSection) return;
    
    const oldContainer = activeSection.querySelector('.old-container');
    const newContainer = activeSection.querySelector('.new-container');
    
    if (!oldContainer || !newContainer) return;
    
    // Remove existing listeners to prevent duplicates
    oldContainer.removeEventListener('scroll', oldContainer.scrollHandler);
    newContainer.removeEventListener('scroll', newContainer.scrollHandler);
    
    // Simple scroll synchronization - since lines are now properly aligned
    oldContainer.scrollHandler = function() {
        newContainer.scrollTop = this.scrollTop;
    };
    
    newContainer.scrollHandler = function() {
        oldContainer.scrollTop = this.scrollTop;
    };
    
    oldContainer.addEventListener('scroll', oldContainer.scrollHandler);
    newContainer.addEventListener('scroll', newContainer.scrollHandler);
}

function toggleFolder(elem) {
    const heading = elem;
    const contents = heading.nextElementSibling;
    if (!contents) return;
    const collapsed = contents.classList.toggle('collapsed');
    heading.classList.toggle('collapsed', collapsed);
    // Change arrow character
    const arrow = heading.querySelector('.folder-arrow');
    if (arrow) {
        arrow.textContent = collapsed ? '\u25B6' : '\u25BC'; // ▶ or ▼
    }
}

function updateFolderCheckboxes() {
    // For each folder-heading, update its checkbox based on all descendant file checkboxes
    document.querySelectorAll('.folder-heading').forEach(folder => {
        const folderCheckbox = folder.querySelector('.folder-checkbox');
        if (!folderCheckbox) return;
        // Find all descendant file checkboxes
        const folderContents = folder.nextElementSibling;
        if (!folderContents) return;
        const fileCheckboxes = folderContents.querySelectorAll('.file-item-checkbox');
        if (fileCheckboxes.length === 0) {
            folderCheckbox.checked = false;
            return;
        }
        let allChecked = true;
        fileCheckboxes.forEach(cb => {
            if (!cb.checked) allChecked = false;
        });
        folderCheckbox.checked = allChecked;
    });
}

// Resizer logic for file explorer
let isResizing = false;
let startX = 0;
let startWidth = 0;
document.addEventListener('DOMContentLoaded', function() {
    // Show first file by default
    const firstFile = document.querySelector('.file-item');
    if (firstFile) {
        const fileId = firstFile.getAttribute('data-file');
        showFile(fileId);
    }
    // Set all arrows to down (open) by default
    document.querySelectorAll('.folder-heading .folder-arrow').forEach(arrow => {
        arrow.textContent = '\u25BC'; // ▼
    });
    // Update folder checkboxes initially
    updateFolderCheckboxes();
    // Add event listeners to file checkboxes
    document.querySelectorAll('.file-item-checkbox').forEach(cb => {
        cb.addEventListener('change', updateFolderCheckboxes);
    });
    // Resizer logic
    const resizer = document.getElementById('sidebar-resizer');
    const sidebar = document.querySelector('.file-explorer');
    if (resizer && sidebar) {
        resizer.addEventListener('mousedown', function(e) {
            isResizing = true;
            startX = e.clientX;
            startWidth = sidebar.offsetWidth;
            resizer.classList.add('active');
            document.body.style.cursor = 'ew-resize';
        });
        document.addEventListener('mousemove', function(e) {
            if (!isResizing) return;
            let newWidth = startWidth + (e.clientX - startX);
            newWidth = Math.max(150, Math.min(600, newWidth));
            sidebar.style.width = newWidth + 'px';
        });
        document.addEventListener('mouseup', function(e) {
            if (isResizing) {
                isResizing = false;
                resizer.classList.remove('active');
                document.body.style.cursor = '';
            }
        });
    }
});
</script>
'''


def parse_diff(diff_lines):
    """
    Parses a unified diff into a list of files, each with hunks and lines.
    Returns: [ { 'filename': str, 'hunks': [ { 'lines': [ (type, old_lineno, new_lineno, text) ] } ] } ]
    """
    files = []
    current_file = None
    current_hunk = None
    old_lineno = new_lineno = None
    for line in diff_lines:
        if line.startswith('diff --git'):
            if current_file:
                if current_hunk:
                    current_file['hunks'].append(current_hunk)
                files.append(current_file)
            current_file = {'filename': line.split()[-1], 'hunks': []}
            current_hunk = None
        elif line.startswith('@@'):
            if current_hunk and current_file:
                current_file['hunks'].append(current_hunk)
            current_hunk = {'lines': []}
            # Parse hunk header: @@ -old,+new @@
            m = re.match(r'@@ -([0-9]+),?([0-9]*) \+([0-9]+),?([0-9]*) @@', line)
            if m:
                old_lineno = int(m.group(1))
                new_lineno = int(m.group(3))
        elif current_hunk is not None:
            if line.startswith('+') and not line.startswith('+++'):
                current_hunk['lines'].append(('added', None, new_lineno, line[1:]))
                if new_lineno is not None:
                    new_lineno += 1
            elif line.startswith('-') and not line.startswith('---'):
                current_hunk['lines'].append(('removed', old_lineno, None, line[1:]))
                if old_lineno is not None:
                    old_lineno += 1
            else:
                if line.startswith(' '):
                    current_hunk['lines'].append(('unchanged', old_lineno, new_lineno, line[1:]))
                    if old_lineno is not None:
                        old_lineno += 1
                    if new_lineno is not None:
                        new_lineno += 1
    if current_file:
        if current_hunk:
            current_file['hunks'].append(current_hunk)
        files.append(current_file)
    return files


def side_by_side_rows(hunk_lines):
    """
    Given hunk lines, yield tuples for side-by-side display: (old_lineno, old_text, new_lineno, new_text, type)
    Ensures unchanged lines are always aligned side by side.
    """
    rows = []
    i = 0
    while i < len(hunk_lines):
        line = hunk_lines[i]
        
        if line[0] == 'unchanged':
            # Unchanged lines always align perfectly
            rows.append((line[1], line[3], line[2], line[3], 'unchanged'))
            i += 1
            
        elif line[0] == 'removed':
            # Check if next line is added (change)
            if i+1 < len(hunk_lines) and hunk_lines[i+1][0] == 'added':
                # This is a change - both lines align
                rows.append((line[1], line[3], hunk_lines[i+1][2], hunk_lines[i+1][3], 'changed'))
                i += 2
            else:
                # This is a pure removal - add blank line on new side
                rows.append((line[1], line[3], '', '', 'removed'))
                i += 1
                
        elif line[0] == 'added':
            # This is a pure addition - add blank line on old side
            rows.append(('', '', line[2], line[3], 'added'))
            i += 1
            
    return rows


def build_dir_tree(files):
    """
    Build a nested dictionary representing the directory tree from a list of files.
    Each node is a dict: { 'folders': {subfolder: node, ...}, 'files': [(file_index, filename), ...] }
    """
    root = {'folders': {}, 'files': []}
    for file_index, f in enumerate(files):
        path = f['filename']
        parts = path.split('/')
        node = root
        for part in parts[:-1]:
            if part not in node['folders']:
                node['folders'][part] = {'folders': {}, 'files': []}
            node = node['folders'][part]
        node['files'].append((file_index, parts[-1]))
    return root


def render_dir_tree(node, parent_path=""):
    html = []
    # Render folders first
    for folder in sorted(node['folders'].keys()):
        folder_id = f"folder-{parent_path}/{folder}".replace('/', '_')
        html.append(
            f'<div class="folder-heading" onclick="toggleFolder(this)">' 
            f'<input type="checkbox" class="folder-checkbox" tabindex="-1" aria-disabled="true">'
            f'<span class="folder-arrow"></span>'
            f'{html_escape(folder)}</div>'
        )
        html.append('<div class="folder-contents">')
        html.append(render_dir_tree(node['folders'][folder], parent_path + '/' + folder))
        html.append('</div>')
    # Render files
    for file_index, filename in node['files']:
        file_id = f"file-{file_index}"
        html.append(
            f'<div class="file-item" data-file="{file_id}" onclick="showFile(\'{file_id}\')">'
            f'<input type="checkbox" class="file-item-checkbox" onclick="event.stopPropagation();">'
            f'{html_escape(filename)}</div>'
        )
    return ''.join(html)


def html_escape(s):
    import html
    return html.escape(s)


def render_html(files):
    html_parts = ["<html><head>", STYLE, "</head><body>"]
    html_parts.append('<div class="container">')
    
    # File explorer sidebar
    html_parts.append('<div class="file-explorer">')
    html_parts.append('<h2>Files</h2>')
    dir_tree = build_dir_tree(files)
    html_parts.append(render_dir_tree(dir_tree))
    html_parts.append('</div>')
    # Add resizer between sidebar and diff-view
    html_parts.append('<div id="sidebar-resizer" class="resizer"></div>')
    
    # Diff view area
    html_parts.append('<div class="diff-view">')
    
    for file_index, f in enumerate(files):
        file_id = f"file-{file_index}"
        html_parts.append(f'<div id="diff-{file_id}" class="diff-section">')
        html_parts.append(f'<h2>{html.escape(f["filename"])}</h2>')
        html_parts.append('<div style="display: flex; gap: 20px;">')
        
        # Collect all lines from all hunks
        all_lines = []
        for hunk in f['hunks']:
            all_lines.extend(hunk['lines'])
        
        # Process all lines together to ensure proper alignment
        old_rows = []
        new_rows = []
        
        i = 0
        while i < len(all_lines):
            line = all_lines[i]
            
            if line[0] == 'unchanged':
                # Unchanged lines always align perfectly
                old_rows.append((line[1], line[3], 'unchanged'))
                new_rows.append((line[2], line[3], 'unchanged'))
                i += 1
                
            elif line[0] == 'removed':
                # Check if next line is added (change)
                if i+1 < len(all_lines) and all_lines[i+1][0] == 'added':
                    # This is a change - both lines align
                    old_rows.append((line[1], line[3], 'changed'))
                    new_rows.append((all_lines[i+1][2], all_lines[i+1][3], 'changed'))
                    i += 2
                else:
                    # This is a pure removal - add blank line on new side
                    old_rows.append((line[1], line[3], 'removed'))
                    new_rows.append(('', '', 'removed'))
                    i += 1
                    
            elif line[0] == 'added':
                # This is a pure addition - add blank line on old side
                old_rows.append(('', '', 'added'))
                new_rows.append((line[2], line[3], 'added'))
                i += 1
        
        # Old code section
        html_parts.append('<div style="flex: 1; min-width: 0;">')
        html_parts.append('<h3>Old Code</h3>')
        html_parts.append('<div class="old-container" style="border: 1px solid #30363d; overflow: auto; max-height: 80vh;">')
        html_parts.append('<table class="diff" style="width: 100%;">')
        html_parts.append('<tr><th>Line</th><th>Code</th></tr>')
        
        for lineno, text, typ in old_rows:
            tr_class = typ if typ in ('added', 'removed', 'unchanged', 'changed') else ''
            html_parts.append(f'<tr class="{tr_class}">')
            html_parts.append(f'<td class="lineno">{lineno if lineno else ""}</td>')
            html_parts.append(f'<td class="code">{html.escape(text)}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</table></div></div>')
        
        # New code section
        html_parts.append('<div style="flex: 1; min-width: 0;">')
        html_parts.append('<h3>New Code</h3>')
        html_parts.append('<div class="new-container" style="border: 1px solid #30363d; overflow: auto; max-height: 80vh;">')
        html_parts.append('<table class="diff" style="width: 100%;">')
        html_parts.append('<tr><th>Line</th><th>Code</th></tr>')
        
        for lineno, text, typ in new_rows:
            tr_class = typ if typ in ('added', 'removed', 'unchanged', 'changed') else ''
            html_parts.append(f'<tr class="{tr_class}">')
            html_parts.append(f'<td class="lineno">{lineno if lineno else ""}</td>')
            html_parts.append(f'<td class="code">{html.escape(text)}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</table></div></div>')
        html_parts.append('</div>')
        html_parts.append('</div>')
    
    html_parts.append('</div>')
    html_parts.append('</div>')
    html_parts.append('</body></html>')
    return '\n'.join(html_parts)


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <diff_file> <output_html>")
        sys.exit(1)
    diff_file, output_html = sys.argv[1], sys.argv[2]
    with open(diff_file, encoding='utf-8') as f:
        diff_lines = f.readlines()
    files = parse_diff(diff_lines)
    html_out = render_html(files)
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_out)
    print(f"Wrote HTML diff to {output_html}")

if __name__ == '__main__':
    main() 