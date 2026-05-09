# 他の conf.d/*.fish より先に PATH を整える
# (fish 単独起動経路では brew shellenv が走らないため、ここで補う)
# alphabetical order で `00-` 接頭辞が最初に評価される
for p in /opt/homebrew/bin /home/linuxbrew/.linuxbrew/bin ~/.local/bin
    test -d $p; and fish_add_path -gp $p
end
