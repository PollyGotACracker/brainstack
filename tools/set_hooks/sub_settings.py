"""brainstack 전역 설정의 단일 원본이다.

install은 이 파일의 리터럴만 사용자 전역 파일에 반영한다.
값을 바꾼 뒤 install을 다시 실행하면 기존 설치에도 바뀐 값이 재반영된다.
<BRAINSTACK>은 install이 이 저장소의 실제 경로로 바꾼다.
"""

# Claude: ~/.claude/settings.json의 단일 값이다.
# agent·statusLine은 교체하고 env는 키별로 병합한다.
CLAUDE_SETTINGS = {
    "agent": "buddy",
    "env": {
        "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"
    },
    "statusLine": {
        "type": "command",
        "command": "python \"<BRAINSTACK>\\hooks\\add_statusline.py\"",
        "padding": 0,
        "statusMessage": "Brainstack 에이전트 상태줄 이름 표시"
    }
}

# Claude: ~/.claude/settings.json permissions에 합집합 병합하며 사용자 allow를 보존한다.
CLAUDE_PERMISSION_RULES = {
    "allow": [
        "WebSearch",
        "WebFetch",
        "Bash(git status *)",
        "Bash(git diff *)",
        "Bash(git log *)",
        "Bash(git show *)",
        "Bash(git branch *)",
        "Bash(stat *)",
        "Bash(date *)",
        "Bash(wc *)",
        "Bash(python tools/check_doc_rule.py)",
        "Bash(python tools/set_skills.py check)",
        "Bash(python ../tools/check_doc_rule.py)",
        "Bash(python ../tools/set_skills.py check)"
    ],
    "ask": [
        "Bash(git checkout *)",
        "Bash(git switch *)",
        "Bash(git restore *)",
        "Bash(git stash *)",
        "Bash(git tag *)",
        "Bash(rm *)",
        "Bash(rmdir *)"
    ],
    "deny": [
        "Agent(fork)",
        "Bash(git commit *)",
        "Bash(git push *)",
        "Bash(git merge *)",
        "Bash(git rebase *)",
        "Bash(git reset *)",
        "Bash(git revert *)",
        "Bash(git cherry-pick *)",
        "Bash(git clean *)",
        "Read(.env)",
        "Read(.env.*)",
        "Read(secrets/**)"
    ]
}

# Codex: ~/.codex/rules/default.rules의 brainstack 블록에 쓰는 15개 실행 정책이다.
# Claude의 Read·Agent 도구 권한을 Codex prefix 규칙으로 확대하지 않는다.
CODEX_RULES_BLOCK = """# >>> brainstack >>>
# tools/set_hooks.py install이 관리하는 블록이다.
# tools/hooks/sub_settings.py CODEX_RULES_BLOCK이 권한 원본이다.
# 승인 요청: git checkout, git switch, git restore, git stash, git tag, rm, rmdir
# 실행 금지: git commit, git push, git merge, git rebase, git reset, git revert, git cherry-pick, git clean
# 사용자 전역 allow는 누적 사용자 설정이며 이 관리 블록에 포함하지 않는다.
# 샌드박스 밖에서 실행되는 명령만 대상이다.

# Source: Bash(git commit *)
prefix_rule(pattern=["git", "commit"], decision="forbidden")

# Source: Bash(git push *)
prefix_rule(pattern=["git", "push"], decision="forbidden")

# Source: Bash(git merge *)
prefix_rule(pattern=["git", "merge"], decision="forbidden")

# Source: Bash(git rebase *)
prefix_rule(pattern=["git", "rebase"], decision="forbidden")

# Source: Bash(git reset *)
prefix_rule(pattern=["git", "reset"], decision="forbidden")

# Source: Bash(git revert *)
prefix_rule(pattern=["git", "revert"], decision="forbidden")

# Source: Bash(git cherry-pick *)
prefix_rule(pattern=["git", "cherry-pick"], decision="forbidden")

# Source: Bash(git clean *)
prefix_rule(pattern=["git", "clean"], decision="forbidden")

# Source: Bash(git checkout *)
prefix_rule(pattern=["git", "checkout"], decision="prompt")

# Source: Bash(git switch *)
prefix_rule(pattern=["git", "switch"], decision="prompt")

# Source: Bash(git restore *)
prefix_rule(pattern=["git", "restore"], decision="prompt")

# Source: Bash(git stash *)
prefix_rule(pattern=["git", "stash"], decision="prompt")

# Source: Bash(git tag *)
prefix_rule(pattern=["git", "tag"], decision="prompt")

# Source: Bash(rm *)
prefix_rule(pattern=["rm"], decision="prompt")

# Source: Bash(rmdir *)
prefix_rule(pattern=["rmdir"], decision="prompt")
# <<< brainstack <<<"""

# Claude: SessionStart·SubagentStart context와 Agent 호출 전 승인 hook이다.
# 이벤트·matcher·명령·옵션·statusMessage를 여기서 직접 확인하고 수정한다.
CLAUDE_HOOK_RULES = {
    "SessionStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "python \"<BRAINSTACK>\\hooks\\load_agent.py\" --default-role buddy",
                    "statusMessage": "Brainstack 메인 에이전트 역할 및 공통 지침"
                }
            ]
        }
    ],
    "SubagentStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "python \"<BRAINSTACK>\\hooks\\load_agent.py\"",
                    "statusMessage": "Brainstack 서브 에이전트 역할 및 공통 지침"
                }
            ]
        }
    ],
    "PreToolUse": [
        {
            "matcher": "Agent",
            "hooks": [
                {
                    "type": "command",
                    "command": "python -c \"import json; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask', 'permissionDecisionReason': 'Subagent call requires user approval'}}))\"",
                    "statusMessage": "Brainstack 서브 에이전트 호출 전 승인"
                }
            ]
        }
    ]
}

# Codex: Role·Persona 주입 hook이다. Windows 명령과 context 한도도 같은 원본이다.
CODEX_HOOK_RULES = {
    "SessionStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "python \"<BRAINSTACK>\\hooks\\load_agent.py\" --include-role --default-role buddy",
                    "commandWindows": "py \"<BRAINSTACK>\\hooks\\load_agent.py\" --include-role --default-role buddy",
                    "additionalContextLimit": 6000,
                    "statusMessage": "Brainstack 메인 에이전트 역할 및 공통 지침"
                }
            ]
        }
    ],
    "SubagentStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "python \"<BRAINSTACK>\\hooks\\load_agent.py\" --include-role",
                    "commandWindows": "py \"<BRAINSTACK>\\hooks\\load_agent.py\" --include-role",
                    "additionalContextLimit": 6000,
                    "statusMessage": "Brainstack 서브 에이전트 역할 및 공통 지침"
                }
            ]
        }
    ]
}

# Git Bash: ~/.bashrc의 brainstack 블록이다. 블록 밖 내용은 바꾸지 않는다.
BASHRC_BLOCK = """# >>> brainstack >>>
# tools/set_hooks.py install이 관리하는 블록이다.
# claude agent <이름> [인자...]: claude --agent <이름> [인자...]로 실행한다.
# codex agent <이름> [인자...]: BRAINSTACK_AGENT=<이름>으로 codex [인자...]를 실행한다.
# claude는 첫 인자가 agent가 아니면 원래 명령에 그대로 전달한다.
# codex는 --no-daemon을 기본 부착하고 나머지 인자를 그대로 전달한다.
claude() {
  if [ "$1" = "agent" ] && [ -n "$2" ]; then
    local name="$2"
    shift 2
    command claude --agent "$name" "$@"
  else
    command claude "$@"
  fi
}

codex() {
  local name=""
  if [ "$1" = "agent" ] && [ -n "$2" ]; then
    name="$2"
    shift 2
  fi
  local arg
  local default_args=(--no-daemon)
  for arg in "$@"; do
    if [ "$arg" = "--no-daemon" ]; then
      default_args=()
      break
    fi
  done
  if [ -n "$name" ]; then
    BRAINSTACK_AGENT="$name" command codex "${default_args[@]}" "$@"
  else
    command codex "${default_args[@]}" "$@"
  fi
}
# <<< brainstack <<<"""

# Claude: ~/.claude/CLAUDE.md에 추가하는 import 한 줄이다.
# <BRAINSTACK>은 슬래시 경로로 바뀐다.
CLAUDE_IMPORT_LINE = "@<BRAINSTACK>/AGENTS.principle.md"
