# Bash completion for appleLoops.py
# by Tony Williams, honestpuck@gmail.com
# version 0.3
# 21/05/2017

_appleLoops() {
  local cur opts
  COMPREPLY=()

  cur="${COMP_WORDS[COMP_CWORD]}"
  opts="--apps --build-dmg --cache-server --debug --destination --deployment \
    --dry-run --hard-link --log-path --mandatory-only --mirror-paths \
    --optional-only --pkg-server --plists --threshold --quiet --version"

  case "$cur" in
    --*)
      COMPREPLY=($(compgen -W "$opts"  "$cur"))
      return
      ;;
  esac
}

complete -o bashdefault -o default -F _appleLoops appleLoops.py
 
