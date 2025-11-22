-- app/confirm_reserve.lua
-- KEYS = [ key1, key2, ... ]
-- ARGV = [ hold_id, owner, booking_id, reserve_ttl_seconds(optional) ]
-- Behavior:
--   - Ensures each key's current value == "<hold_id>|<owner>"
--   - If all match, sets each key to "RESERVED:<booking_id>" and optional TTL
--   - If any mismatch, does not change any key and returns list of mismatches
-- Return:
--   { "1" } on success
--   { "0", <n_mismatch>, key1, key2, ... } on failure

local hold_id = ARGV[1]
local owner = ARGV[2] or ""
local booking_id = ARGV[3]
local ttl = tonumber(ARGV[4])

local expected = hold_id .. "|" .. owner
local mismatches = {}

for i, key in ipairs(KEYS) do
	local cur = redis.call('GET', key)
	if cur ~= expected then
		table.insert(mismatches, key)
	end
end

if #mismatches > 0 then
	local res = { "0", tostring(#mismatches) }
	for i, k in ipairs(mismatches) do table.insert(res, k) end
	return res
end

-- All matched, set reserved values
for i, key in ipairs(KEYS) do
	local reserved_val = "RESERVED:" .. booking_id
	if ttl then
		redis.call('SET', key, reserved_val)
		redis.call('EXPIRE', key, ttl)
	else
		redis.call('SET', key, reserved_val)
	end
end

return { "1" }