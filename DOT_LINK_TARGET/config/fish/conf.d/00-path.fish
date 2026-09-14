# 他の conf.d/*.fish より先に PATH を整える
# (fish 単独起動経路では brew shellenv が走らないため、ここで補う)
# alphabetical order で `00-` 接頭辞が最初に評価される
for p in /opt/homebrew/bin /home/linuxbrew/.linuxbrew/bin ~/.local/bin
    test -d $p; and fish_add_path -gp $p
end

# Docker Desktop の CLI（docker 本体と cli-plugins）
# Docker Desktop が config.fish へ直接追記してくるのを避け、ここで一元管理する
test -d ~/.docker/bin; and fish_add_path -ga ~/.docker/bin
