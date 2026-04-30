local config = require("snakefmt.config")
local paths = require("snakefmt.paths")
local M = {}

local group = vim.api.nvim_create_augroup("snakefmt", { clear = true })

function M.setup(opts)
  config.setup(opts)
  vim.api.nvim_clear_autocmds({ group = group })
  if config.options.auto_format then
    vim.api.nvim_create_autocmd("BufWritePre", {
      group = group,
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
  local cmd = paths.get_snakefmt_bin(config.options)
  if not cmd then
    vim.notify("snakefmt: binary not found and uvx fallback failed", vim.log.levels.ERROR)
    return
  end

  local bufnr = vim.api.nvim_get_current_buf()
  local content = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  local stdin = table.concat(content, "\n") .. "\n"

  -- Build command args (make a copy of cmd table to avoid modifying original)
  local full_cmd = vim.list_extend({}, cmd)
  if config.options.line_length then
    table.insert(full_cmd, "--line-length")
    table.insert(full_cmd, tostring(config.options.line_length))
  end
  table.insert(full_cmd, "-")

  vim.system(full_cmd, { stdin = stdin }, function(obj)
    vim.schedule(function()
      if obj.code == 0 then
        local formatted = vim.split(obj.stdout, "\n")
        if formatted[#formatted] == "" then
          table.remove(formatted)
        end
        vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, formatted)
        vim.notify("snakefmt: formatted", vim.log.levels.INFO)
      else
        vim.notify("snakefmt error: " .. obj.stderr, vim.log.levels.ERROR)
      end
    end)
  end)
end

return M
