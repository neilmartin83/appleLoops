# Bash completion for appleLoops.py
# by Tony Williams, honestpuck@gmail.com
# version 0.3
# 21/05/2017

_appleLoops() {
  local cur opts
  COMPREPLY=()

  cur="${COMP_WORDS[COMP_CWORD]}"
  opts="--apps --build-dmg --cache-server --destination --deployment --dry-run \
    --mandatory-only --mirror-paths --optional-only --pkg-server --plists --quiet" 

  case "$cur" in
    --*)
      COMPREPLY=($(compgen -W "$opts"  "$cur"))
      return
      ;;
  esac
}

complete -o bashdefault -o default -F _appleLoops appleLoops.py
 
