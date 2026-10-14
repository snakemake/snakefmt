local M = {}

function M.get_snakefmt_bin(config_opts)
  -- 1. Manual override
  if config_opts.bin_path and vim.fn.executable(config_opts.bin_path) == 1 then
    return { config_opts.bin_path }
  end

  -- 2. Local Environment ($VIRTUAL_ENV)
  local venv = os.getenv("VIRTUAL_ENV")
  if venv then
    local candidates = {
      venv .. "/bin/snakefmt",
      venv .. "/Scripts/snakefmt.exe",
      venv .. "/Scripts/snakefmt",
    }
    for _, path in ipairs(candidates) do
      if vim.fn.executable(path) == 1 then
        return { path }
      end
    end
  end

  -- 3. Project Environment (.venv)
  local project_venv = vim.fn.finddir(".venv", ".;")
  if project_venv ~= "" then
    local venv_base = vim.fn.fnamemodify(project_venv, ":p")
    local candidates = {
      venv_base .. "bin/snakefmt",
      venv_base .. "Scripts/snakefmt.exe",
      venv_base .. "Scripts/snakefmt",
    }
    for _, path in ipairs(candidates) do
      if vim.fn.executable(path) == 1 then
        return { path }
      end
    end
  end

  -- 4. Global Path
  if vim.fn.executable("snakefmt") == 1 then
    return { "snakefmt" }
  end

  -- 5. uvx fallback
  if config_opts.uvx_fallback and vim.fn.executable("uv") == 1 then
    return { "uv", "run", "--with", "snakefmt", "snakefmt" }
  end

  return nil
end

return M
