function fishes_update -d "fish関連の更新をする(fisherやfishの補完等)"
    # fisher関係のupdate
    fisher update

    # fishの補完を更新
    ## https://fishshell.com/docs/current/commands.html#fish_update_completions
    fish_update_completions
end
