/**
 * 「看过免费 Key 提示」的设备级标记。
 *
 * 只有一个事实（看过／没看过），所以不建服务、不建 store：读一次、写一次，
 * 两个纯函数加一个最小的存储接口。存储接口只声明用到的那两个方法，测试可以传
 * 一个内存实现，浏览器里传 `window.localStorage`。
 *
 * 读失败一律按「没看过」处理：隐私模式或存储被禁用时 `localStorage` 会抛异常，
 * 这时提示最多多弹一次，比整个设置页崩掉可接受。
 */

/** 这一层用到的 `localStorage` 子集；隔离出来是为了让测试不碰真实存储。 */
export interface NoticeFlagStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/**
 * 取浏览器存储；拿不到（没有 window、被禁用）时返回 undefined。
 * @returns 可用存储，或 undefined。
 */
export function browserNoticeStorage(): NoticeFlagStorage | undefined {
  try {
    const storage = globalThis.localStorage
    return storage === undefined ? undefined : { getItem: key => storage.getItem(key), setItem: (key, value) => { storage.setItem(key, value) } }
  } catch (_blocked) {
    // 访问 `localStorage` 本身在受限环境会抛 SecurityError。
    return undefined
  }
}

/**
 * 读标记。任何异常与空值都算「没看过」。
 * @param storage - 目标存储；缺失视为没看过。
 * @param key - 标记键。
 * @returns 是否已看过。
 */
export function readNoticeSeen(storage: NoticeFlagStorage | undefined, key: string): boolean {
  if (storage === undefined) return false
  try {
    return storage.getItem(key) === '1'
  } catch (_blocked) {
    return false
  }
}

/**
 * 写标记。写失败不抛：提示已经显示过了，这次没记下来只是下次会再弹一次。
 * @param storage - 目标存储；缺失时什么都不做。
 * @param key - 标记键。
 * @returns 是否写入成功。
 */
export function writeNoticeSeen(storage: NoticeFlagStorage | undefined, key: string): boolean {
  if (storage === undefined) return false
  try {
    storage.setItem(key, '1')
    return true
  } catch (_blocked) {
    // 配额满或被禁用：不阻断用户，下次再弹。
    return false
  }
}
