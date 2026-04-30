local config = require("snakefmt.config")
local M = {}
function M.setup(opts)
  config.setup(opts)
  if config.options.auto_format then
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "snakemake",
      callback = function()
        vim.api.nvim_create_autocmd("BufWritePre", {
          buffer = 0,
          callback = function()
            M.format()
          end,
        })
      end,
    })
  end
  vim.api.nvim_create_user_command("Snakefmt", function()
    M.format()
  end, {})
end
function M.format()
  -- To be implemented in next tasks
  print("Snakefmt triggered")
end
return M
