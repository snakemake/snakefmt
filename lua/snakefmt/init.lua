local config = require("snakefmt.config")
local M = {}
function M.setup(opts)
  config.setup(opts)
  if config.options.auto_format then
    vim.api.nvim_create_autocmd("BufWritePre", {
      pattern = { "*.smk", "Snakefile" },
      callback = function()
        M.format()
      end,
      desc = "Auto-format with snakefmt on save",
    })
  end

  vim.api.nvim_create_user_command("Snakefmt", function()
    M.format()
  end, { desc = "Format current buffer with snakefmt" })
end
function M.format()
  -- To be implemented in next tasks
  print("Snakefmt triggered")
end
return M
