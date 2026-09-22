# Shell 脚本导出换行约束

状态：implemented
类型：bug-fix
Owner：.gitattributes

## 问题

Windows 启用 core.autocrlf 后，git archive 将仓库内 LF 脚本导出为 CRLF；Linux 执行初始化脚本失败。仅检查 Git blob 或对测试副本临时转换不能证明交付包可执行。

## 决策

通过 Git 属性将所有 .sh 文件固定为 LF。新增使用临时 Git 仓库实际导出的测试，覆盖 core.autocrlf=true 与 false。

## 替代方案

要求每位开发者关闭 autocrlf 依赖个人配置；在发布脚本中转换会遗漏其他源码导出入口。

## 验证

| 验收主张 | 失败面 | 语义 Owner | 直接证据 / 命令 | 负向案例 | 当前结果 |
|---|---|---|---|---|---|
| Shell 导出保持 LF | Windows 产生 Linux 不可执行脚本 | .gitattributes | 真实 git archive 字节断言、Linux 初始化测试 | 去掉属性且开启 autocrlf 时导出 CRLF | Passed |

## 后果

只限定 shell 脚本，不改变其他文件的换行策略；已有工作副本需重新检出或显式转换才能刷新本地字节。

Windows 真实 Git 导出测试 3 项通过。Linux 完整回归中的 shell 初始化检查通过。
