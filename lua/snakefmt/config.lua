local M = {}
M.defaults = {
  auto_format = false,
  line_length = nil,
  bin_path = nil,
  uvx_fallback = true,
}
M.options = {}
function M.setup(opts)
  M.options = vim.tbl_deep_extend("force", M.defaults, opts or {})
end
return M
