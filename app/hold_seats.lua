-- app/hold_seats.lua
-- Usage:
-- KEYS = [ key1, key2, ... ]
-- ARGV = [ hold_id, ttl_seconds, owner ]
-- Sets each key's value to "<hold_id>|<owner>" if current value == "AVAILABLE" OR equals current hold value (idempotent).
-- Returns:
--   { "1" } on success
--   { "0", <n_unavailable>, key1, key2, ... } on failure

local hold_id = ARGV[1]
local ttl = tonumber(ARGV[2]) or 600
local owner = ARGV[3] or ""

local hold_val = hold_id .. "|" .. owner

local unavailable = {}
for i, key in ipairs(KEYS) do
	local cur = redis.call('GET', key)
	if not cur then
	-- treat missing as AVAILABLE and set hold
		redis.call('SET', key, hold_val)
		redis.call('EXPIRE', key, ttl)
	else
		if cur == "AVAILABLE" then
			redis.call('SET', key, hold_val)
			redis.call('EXPIRE', key, ttl)
		else
		-- If cur already equals our hold_val, allow (idempotent re-hold by same hold_id+owner)
			if cur == hold_val then
				redis.call('EXPIRE', key, ttl)
			else
				table.insert(unavailable, key)
			end
		end
	end
end

if #unavailable == 0 then
	return { "1" }
else
	local res = { "0", tostring(#unavailable) }
	for i, k in ipairs(unavailable) do table.insert(res, k) end
	return res
end