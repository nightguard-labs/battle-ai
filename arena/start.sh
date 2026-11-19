#!/bin/bash
# Lay out the battlefield fresh, then idle. Homes: root-owned files, group "arena" may EDIT them;
# sticky + root-owned = nobody can delete, rename or chmod the other's files. Stashes (/home/fighter_x) are private.
for f in a b; do
  mkdir -p /arena/$f
  cp /arena-seed/persona_$f.md /arena/$f/persona.md
  cp /arena-seed/notes.md      /arena/$f/notes.md
  cp /arena-seed/config.json   /arena/$f/config.json
  chown -R root:arena /arena/$f; chmod 664 /arena/$f/*; chmod 1775 /arena/$f
done
chmod 755 /arena
exec sleep infinity
