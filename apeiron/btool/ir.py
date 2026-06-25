from stracelit.tracer import NodeType as ACTNodeType
from typing import Dict, List
from dataclasses import dataclass, field, asdict    
import datetime as dt
import json
import subprocess 
import re  
from pathlib import Path
from enum import Enum
import apeiron.utils as U
import os


@dataclass
class ACTNode:
    # Abstract Component Tree Node
    id: str
    level: str
    component: str
    parent_id: str
    source_code: str
    params: dict
    children: list['ACTNode'] = field(default_factory=list)  # List of child nodes

    def to_dict(self):
        """
        Convert the ACTNode to a dictionary representation.
        """
        return {
            'id': self.id,
            'level': self.level.value if not isinstance(self.level, str) else self.level,
            'component': self.component,
            'parent_id': self.parent_id,
            'source_code': self.source_code,
            'params': self.params,
            'children': []  # Store only IDs of children
        }


class ACTActionSide(Enum):
    APP = 'app'
    USER = 'user'

@dataclass
class ACTAction:
    node_id: str
    timestamp: dt.datetime
    action: str
    value: dict
    side: ACTActionSide = ACTActionSide.APP 

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = dt.datetime.fromisoformat(self.timestamp)

    def to_dict(self):
        """
        Convert the ACTAction to a dictionary representation.
        """
        return {
            'node_id': self.node_id,
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'value': self.value,
            'side': self.side.value if isinstance(self.side, ACTActionSide) else self.side
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create an ACTAction from a dictionary representation.
        """
        return cls(
            node_id=data['node_id'],
            timestamp=dt.datetime.fromisoformat(data['timestamp']),
            action=data['action'],
            value=data['value'],
            side=ACTActionSide(data['side']) if 'side' in data else ACTActionSide.APP
        )

@dataclass
class CUAReport:
    full_report: str
    persona: dict
    demand: dict    

    def __str__(self):
        _str = f"### User Background\n"
        _str += f"  User Persona: {self.persona}\n"
        _str += f"  Task in demand: {self.demand}\n\n"
        _str += f"### User Report\n"
        _str += f"{self.full_report}\n"
        return _str
    
    def to_dict(self):
        return asdict(self)

@dataclass
class ACTTrace:
    actions: list[ACTAction]
    session_start: dt.datetime
    cua_report: CUAReport = None  # Placeholder for CUA report, if needed

    def __post_init__(self):
        self.actions.sort(key=lambda x: x.timestamp)

    @classmethod
    def from_trace(cls, actions, session_start, nodes=None, cua=None):
        actions = [ACTAction(
            node_id=action['path'].replace('root > ', ''),
            timestamp=action['timestamp'],
            action=action['action'],
            value=action['value']
        ) for action in actions]
        if nodes:
            for action in actions:
                if action.node_id not in nodes and action.node_id != 'navigation':
                    # raise ValueError(f"Node ID {action.node_id} not found in provided nodes.")
                    continue
        if cua:
            cua_actions = cua['actions']
            report = cua['report']
            metadata = cua['metadata']
            persona=metadata['persona']
            persona.pop('demands', None)  # Remove 'demands' if it exists
            cua_report = CUAReport(
                full_report=report,
                persona=persona,
                demand=metadata['demand']
            )
            for cua_action in cua_actions:
                action = json.loads(cua_action['action'])['action']
                if action.get('type', None) in ['screenshot', 'wait']:
                    continue
                timestamp = dt.datetime.fromisoformat(cua_action['timestamp'])
                actions.append(ACTAction(
                    node_id=None,
                    timestamp=timestamp,
                    action=action,
                    value=None,
                    side=ACTActionSide.USER
                ))
        session_start = dt.datetime.fromisoformat(session_start)
        return cls(actions=actions, session_start=session_start, cua_report=cua_report if cua else None)
    
    def to_str(self, base_dir=None):
        _str = ''
        for action in self.actions:
            timestamp = action.timestamp.isoformat()
            if action.side == ACTActionSide.USER:
                _str += f"[{timestamp}] User action: {action.action}\n"
            else:
                node_id_short = action.node_id.replace(base_dir, '') if base_dir else action.node_id
                _str += f"[{timestamp}] Received by app: {node_id_short} - {action.action} - {action.value}\n"
        if self.cua_report:
            _str += '\n\n' + self.cua_report.__str__()
        return _str
    
    def to_dict(self):
        """
        Convert the ACTTrace to a dictionary representation.
        """
        return {
            'actions': [action.to_dict() for action in self.actions],
            'session_start': self.session_start.isoformat(),
            'cua_report': self.cua_report.to_dict() if self.cua_report else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create an ACTTrace from a dictionary representation.
        """
        actions = [ACTAction.from_dict(action) for action in data['actions']]
        session_start = dt.datetime.fromisoformat(data['session_start'])
        cua_report = data.get('cua_report',None)
        if cua_report:
            cua_report = CUAReport(
                full_report=cua_report['full_report'],
                persona=cua_report['persona'],
                demand=cua_report['demand']
            )
        return cls(actions=actions, session_start=session_start, cua_report=cua_report)
    
@dataclass
class ACT:
    # Abstract Component Tree
    root: ACTNode = None  # Root node of the tree
    nodes: Dict[str, ACTNode] = field(default_factory=dict)  # Dictionary of nodes indexed by their id
    traces: list[ACTTrace] = field(default_factory=list)
    base_dir: str = None
    default_page: str = None

    def __post_init__(self):
        self.root = ACTNode(id='root', level=ACTNodeType.ROOT, component='Root', parent_id=None, source_code='', params={})
        self.nodes['root'] = self.root  # Initialize the root node
        for node in self.nodes:
            _node = self.nodes[node]
            _parent = _node.parent_id
            if _parent and _parent in self.nodes and _node not in self.nodes[_parent].children:
                self.nodes[_parent].children.append(_node)

    def add_node(self, node: ACTNode):
        assert node.parent_id in self.nodes, f"Parent id {node.parent_id} not found in nodes."
        if node.id not in self.nodes:
            self.nodes[node.id] = node
            self.nodes[node.parent_id].children.append(node)

    def load_trace(self, actions, session_start, cua=None, skip_unfinished=True):
        if skip_unfinished and cua and cua.get('report', None) is None:
            return  # Skip unfinished traces if CUA report is not available
        self.traces.append(ACTTrace.from_trace(actions, session_start, nodes=self.nodes, cua=cua))
    
    def update_tree(self, tree): 
        node_by_file = {}
        for _, v in tree['tree'].items():
            if ':' not in v['id']:
                continue # or handle error appropriately
            
            # rsplit (not split) so a Windows drive-letter colon in the path
            # (e.g. 'C:\\...\\app.py:5') is not mistaken for the file:line separator.
            file, lines_str = v['id'].rsplit(':', 1)
            lines = [int(i.strip()) for i in lines_str.split('->')]
            
            if file not in node_by_file:
                node_by_file[file] = []
            
            node_by_file[file].append({
                'node': ACTNode(
                    id=v['id'],
                    level=v['level'],
                    component=v['component'],
                    parent_id='root',
                    source_code=v['source_code'],
                    params=v['params']
                ), 
                'lines': lines
            })

        # Process each file's nodes to build the coverage tree
        for file in node_by_file:
            nodes_in_file = node_by_file[file]
            nodes_in_file.sort(key=lambda x: x['lines'][0])
            
            for i in range(len(nodes_in_file)):
                current_data = nodes_in_file[i]
                current_node = current_data['node']
                current_to_line = current_data['lines'][1]

                for j in range(i - 1, -1, -1):
                    parent_candidate_data = nodes_in_file[j]
                    parent_candidate_to_line = parent_candidate_data['lines'][1]
                    
                    if parent_candidate_to_line >= current_to_line:
                        current_node.parent_id = parent_candidate_data['node'].id
                        break # Stop searching, we found the closest one.
                
                self.add_node(current_node)
    
    def __str__(self):
        _str = '# App Component Tree\n\n'
        def print_node(_str, node, level=0):
            id_short = node.id.replace(self.base_dir, '') if self.base_dir else node.id
            level_str = str(node.level).replace('NodeType.', '')
            _str += '    ' * level + f" - {id_short} ({level_str} > {node.component})\n"
            for child in node.children:
                _str = print_node(_str, child, level + 1)
            return _str
        _str = print_node(_str, self.root)
        if self.default_page:
            _str += '\nDefault Page: ' + self.default_page

        if self.traces:
            _str += '\n\n\n# User Traces\n\n'
            for idx, trace in enumerate(self.traces):
                _str += f"## Trace {idx}\n\n"
                _str += trace.to_str(base_dir=self.base_dir)
                _str += '\n\n'
        return _str
    
    @property
    def prompt(self):
        _prompt = self.__str__()
        _prompt += '''\n\nNOTE: The component tree may not be complete, it may only provides a partial view of the application's structure. 
It maps the paths in the app responses in the traces to the actual responsive component.'''
        return _prompt

    def to_dict(self):
        """
        Convert the ACT to a dictionary representation.
        """
        return {
            'root': self.root.to_dict(),
            'nodes': {k: v.to_dict() for k, v in self.nodes.items()},
            'traces': [trace.to_dict() for trace in self.traces],
            'base_dir': self.base_dir,
            'default_page': self.default_page
        }

    @classmethod
    def from_dict(cls, data):
        """
        Create an ACT from a dictionary representation.
        """
        # root = ACTNode(**data['root'])
        # nodes = {k: ACTNode(**v) for k, v in data['nodes'].items()}
        nodes = {}
        for k, v in data['nodes'].items():
            # Convert string back to ACTNodeType enum before creating the node
            if isinstance(v['level'], str):
                try:
                    v['level'] = ACTNodeType(v['level']) 
                except Exception as e:
                    for _type in ACTNodeType:
                        if v['level'] == str(_type):
                            v['level'] = _type
                            break
            nodes[k] = ACTNode(**v)

        root = nodes.get('root') # Safely get the root after all nodes are processed

        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)

        traces = [ACTTrace.from_dict(trace) for trace in data['traces']]
        act = cls(root=root, nodes=nodes, traces=traces, base_dir=data.get('base_dir'), default_page=data.get('default_page'))
        return act
    
    @classmethod
    def from_trace_dir(cls, trace_dir: str):
        """
        Load an ACT from a directory containing trace files.
        """
        act = cls()
        for _trace in os.listdir(trace_dir):
            _trace_dir = os.path.join(trace_dir, _trace)
            if not os.path.isdir(_trace_dir):
                continue
            actions = U.load_jsonl(U.pjoin(_trace_dir, 'actions.jsonl'))
            meta = U.load_jsonl(U.pjoin(_trace_dir, 'meta.jsonl'))
            tree = U.load_json(U.pjoin(_trace_dir, 'tree.jsonl'))
            cua = U.load_json(U.pjoin(_trace_dir, '.cua', 'cua_session.json'))

            metadata = {v['meta_type']:v['value'] for v in meta}
            base_dir = metadata['BASE_DIR']['base_dir']
            default_page = metadata['DEFAULT_PAGE']
            session_start = metadata['SESSION_START']['timestamp']
            
            act.update_tree(tree)
            act.base_dir = base_dir
            act.default_page = default_page
            act.load_trace(actions, session_start, cua)
        return act

@dataclass
class ACTDiff:
    old_act: ACT
    new_act: ACT
    new_nodes: list = None
    removed_nodes: list = None
    changed_nodes: list = None

    def __post_init__(self):
        _new_node_ids = list(self.new_act.nodes.keys())
        _old_node_ids = list(self.old_act.nodes.keys())
        self.new_nodes = [node_id for node_id in _new_node_ids if node_id not in _old_node_ids]
        self.removed_nodes = [node_id for node_id in _old_node_ids if node_id not in _new_node_ids]
        self.changed_nodes = []
        for node_id in _new_node_ids:
            if node_id in _old_node_ids:
                new_node: ACTNode = self.new_act.nodes[node_id]
                old_node: ACTNode = self.old_act.nodes[node_id]
                if new_node.component != old_node.component or new_node.source_code != old_node.source_code:
                    self.changed_nodes.append(node_id)
        self.remained_nodes = [node_id for node_id in _old_node_ids if node_id not in self.removed_nodes and node_id not in self.changed_nodes]

    @property
    def turnover_rate(self):
        _old_act_ids = list(self.old_act.nodes.keys())
        if len(_old_act_ids) == 0:
            return 0.0
        n_turnover = (len(self.new_nodes) + len(self.removed_nodes)) #+ len(self.changed_nodes)
        return n_turnover / len(_old_act_ids)
    
    @classmethod
    def from_trace_dirs(cls, old_trace_dir: str, new_trace_dir: str):
        """
        Create an ACTDiff from two directories containing trace files.
        """
        old_act = ACT.from_trace_dir(old_trace_dir)
        new_act = ACT.from_trace_dir(new_trace_dir)
        return cls(old_act=old_act, new_act=new_act)



class FileStatus(Enum):
    ADDED = "added" # new file
    DELETED = "deleted"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"

@dataclass
class FileDiff:
    """Holds the analysis of a single file's changes."""
    file_path: Path
    added_lines: int = 0
    removed_lines: int = 0
    old_line_count: int = 0
    new_line_count: int = 0

    @property
    def status(self) -> FileStatus:
        if self.old_line_count > 0 and self.new_line_count == 0:
            return FileStatus.DELETED
        elif self.old_line_count == self.new_line_count:
            return FileStatus.UNCHANGED
        elif self.old_line_count == 0 and self.new_line_count > 0:
            return FileStatus.ADDED
        else:
            return FileStatus.MODIFIED

@dataclass
class FolderDiff:
    """Holds the complete result of a folder comparison."""
    old_folder: Path 
    new_folder: Path 
    file_diffs: List[FileDiff] = field(default_factory=list)

    def _count_lines(file_path: Path) -> int:
        """Helper to count lines in a file, returning 0 if it doesn't exist."""
        try:
            with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0

    @classmethod
    def from_folders(cls, old_folder_dir: str, new_folder_dir: str, ext = ['.py']):
        folder1 = Path(old_folder_dir)
        folder2 = Path(new_folder_dir)

        # Verify that both paths are valid directories
        if not folder1.is_dir() or not folder2.is_dir():
            print(f"❌ Error: One or both paths are not valid directories ('{folder1}', '{folder2}')")
            return None

        # The command to execute. --unified=0 removes context lines, simplifying parsing.
        command = ['git', 'diff', '--no-index', '--unified=0', str(folder1), str(folder2)]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # git diff exits with 1 if differences are found
            encoding='utf-8'
        )
        
        # git diff exits with 0 for no diffs, 1 for diffs, >1 for an error.
        if result.returncode > 1:
            print("An error occurred while running git diff:")
            print(result.stderr)
            return None
        
        if result.returncode == 0:
            # The folders are identical, return an empty result object
            return cls(old_folder=folder1, new_folder=folder2)

        # --- Begin Parsing the Diff Output ---
        diff_result = cls(old_folder=folder1, new_folder=folder2)

        raw_file_diffs = result.stdout.strip().split('\ndiff --git ')[1:]

        for file_diff_text in raw_file_diffs:
            path_a_match = re.search(r'^--- a/(.+?)$', file_diff_text, re.MULTILINE)
            path_b_match = re.search(r'^\+\+\+ b/(.+?)$', file_diff_text, re.MULTILINE)

            # If we can't find these lines, it's a binary diff or file mode change.
            if not path_a_match or not path_b_match:
                first_line = file_diff_text.split('\n', 1)[0]
                try:
                    file_path_guess = first_line.split(' ')[1].replace(f'b/{folder2.name}/', '')
                    # diff_result.unparsed_changes.append(file_path_guess)
                except IndexError:
                    # diff_result.unparsed_changes.append("(Unknown file)")
                    continue # Skip to the next file diff

            lines = file_diff_text.split('\n')
            
            old_path_str = path_a_match.group(1) if path_a_match else None
            new_path_str = path_b_match.group(1) if path_b_match else None

            # Determine status and file path
            if new_path_str and old_path_str and new_path_str != old_path_str:
                file_path = Path(new_path_str)
                status = 'modified' # Or handle as rename
            elif new_path_str:
                file_path = Path(new_path_str)
                status = 'added' # if old_path_str and 'dev/null' in old_path_str else 'modified'
            elif old_path_str:
                file_path = Path(old_path_str)
                status = 'deleted'
            else:
                continue # Should not happen

            if not file_path.suffix in ext:
                continue

            # Count added/removed lines
            added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))

            # Get total line counts from actual files
            if not file_path.is_absolute():
                file_path = Path('/') / file_path
            old_line_count = cls._count_lines(file_path) if status != 'added' else 0
            # new_line_count = cls._count_lines(folder2 / file_path) if status != 'deleted' else 0
            new_line_count = old_line_count + added - removed if status != 'deleted' else 0

            file_diff_obj = FileDiff(
                file_path=file_path,
                added_lines=added,
                removed_lines=removed,
                old_line_count=old_line_count,
                new_line_count=new_line_count,
            )
            
            diff_result.file_diffs.append(file_diff_obj)

        return diff_result

    @property
    def total_added_lines(self) -> int:
        return sum(f.added_lines for f in self.file_diffs)

    @property
    def total_removed_lines(self) -> int:
        return sum(f.removed_lines for f in self.file_diffs)
    
    @property
    def total_old_lines(self) -> int:
        return sum(f.old_line_count for f in self.file_diffs)

    @property
    def total_new_lines(self) -> int:
        return sum(f.new_line_count for f in self.file_diffs)

    @property
    def total_line_changes(self) -> int:
        return self.total_added_lines + self.total_removed_lines

    @property
    def turnover_rate(self) -> float:
        """Returns the ratio of modified lines to total lines in the old folder."""
        if self.total_old_lines == 0:
            return 0.0
        return self.total_line_changes / self.total_old_lines

    @property
    def modified_files(self) -> List[FileDiff]:
        """Returns a list of files that were modified."""
        return [f for f in self.file_diffs if f.status == FileStatus.MODIFIED]
    
    @property
    def added_files(self) -> List[FileDiff]:
        """Returns a list of files that were added."""
        return [f for f in self.file_diffs if f.status == FileStatus.ADDED]
    
    @property
    def deleted_files(self) -> List[FileDiff]:
        """Returns a list of files that were deleted."""
        return [f for f in self.file_diffs if f.status == FileStatus.DELETED]

    def __str__(self) -> str:
        """Provides a user-friendly summary of the diff results."""
        if not self.modified_files and not self.added_files and not self.deleted_files:
            return "✅ The folders are identical."

        summary = [f"Comparison between '{self.old_folder}' and '{self.new_folder}':"]
        summary.append("-" * 40)
        
        if self.added_files:
            summary.append(f"📦 Added Files ({len(self.added_files)}):")
            for f in self.added_files:
                summary.append(f"  + {f.file_path} ({f.new_line_count} lines)")
        
        if self.deleted_files:
            summary.append(f"\n🗑️ Deleted Files ({len(self.deleted_files)}):")
            for f in self.deleted_files:
                summary.append(f"  - {f.file_path} ({f.old_line_count} lines)")

        if self.modified_files:
            summary.append(f"\n📝 Modified Files ({len(self.modified_files)}):")
            for f in self.modified_files:
                summary.append(
                    f"  ~ {f.file_path} "
                    f"(++{f.added_lines}, --{f.removed_lines}) "
                    f"[{f.old_line_count} -> {f.new_line_count} lines]"
                )

        summary.append("-" * 40)
        summary.append(
            f"Total: ++{self.total_added_lines} lines added, "
            f"--{self.total_removed_lines} lines removed."
            f" Total line changes: {self.total_line_changes} ({self.total_old_lines} -> {self.total_new_lines})."
            f" Turnover rate: {self.turnover_rate:.2%}."
        )
        return "\n".join(summary)
