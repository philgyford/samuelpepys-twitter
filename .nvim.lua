-- Set textwidth for .txt files in this project
-- Requires vim.opt.exrc = true
vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
	pattern = "*.txt",
	callback = function()
		vim.opt_local.textwidth = 299
	end,
})
