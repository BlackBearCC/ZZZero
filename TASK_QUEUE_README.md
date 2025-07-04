# 🔄 任务队列功能说明

## 功能概述

任务队列系统允许您将多个剧情生成任务排队执行，实现批量自动化剧情生成。

## 主要特性

### ✨ 核心功能
- **任务队列管理**：添加、删除、调整任务顺序
- **自动排队执行**：上一个任务完成后自动开始下一个
- **实时状态监控**：队列状态、当前任务、下一个任务
- **任务优先级**：支持设置任务优先级
- **执行结果保存**：所有结果自动保存到数据库

### 🎯 使用场景
- **批量剧情生成**：一次性配置多个不同角色组合的剧情
- **夜间批处理**：设置好队列，让系统夜间自动执行
- **实验对比**：同一配置生成多个版本进行比较
- **角色轮换**：为不同角色组合生成专属剧情

## 使用方法

### 1. 添加任务到队列

1. 前往 **🎭 剧情生成工作流** 页面
2. 配置剧情参数：
   - 选择参与角色
   - 选择剧情地点  
   - 设置剧情数量
   - 选择剧情类型和长度
   - 设置关系深度
3. 点击 **➕ 添加到队列** 按钮
4. 系统自动生成任务名称并添加到队列

### 2. 管理任务队列

前往 **🔄 任务队列** 页面进行管理：

#### 队列控制
- **▶️ 启动队列**：开始自动执行任务
- **⏸️ 停止队列**：暂停队列执行
- **🧹 清除已完成**：清理已完成的任务
- **🔄 刷新**：更新队列状态

#### 任务操作
- **🗑️ 删除任务**：移除待执行的任务
- **⬆️ 上移**：提高任务优先级
- **⬇️ 下移**：降低任务优先级
- **点击任务行**：查看任务详细信息

### 3. 监控执行状态

队列页面实时显示：

#### 队列状态指示器
- 🟢 **运行中**：队列正在自动执行任务
- 🔴 **已停止**：队列暂停，不会自动执行

#### 任务状态说明
- ⏳ **等待中**：任务在队列中等待执行
- 🔄 **执行中**：任务正在生成剧情
- ✅ **已完成**：任务执行成功
- ❌ **失败**：任务执行失败
- 🚫 **已取消**：任务被用户取消

#### 统计信息
- **总任务数**：队列中所有任务数量
- **等待执行**：待执行任务数量  
- **正在执行**：当前执行中的任务数
- **已完成**：成功完成的任务数
- **执行失败**：失败的任务数

## 技术实现

### 系统架构
```
故事工作流页面 → 任务配置 → 添加到队列
                                    ↓
任务队列页面 ← 队列管理器 ← 任务执行器
                ↓                  ↓
            数据库存储 ← 剧情生成工作流
```

### 核心组件
- **TaskQueue**：任务队列管理器
- **QueueTask**：任务数据结构
- **TaskQueueInterface**：队列管理界面
- **QueueHandlers**：队列事件处理器

### 数据持久化
- 任务配置自动保存
- 执行结果存储到数据库
- 支持CSV格式导出
- 任务历史记录保留

## 最佳实践

### 📋 任务规划
1. **合理设置队列大小**：建议单次不超过10个任务
2. **错峰执行**：避免在系统繁忙时启动大量任务
3. **配置验证**：添加任务前确认配置正确

### ⚡ 性能优化  
1. **优先级设置**：重要任务设置高优先级
2. **资源管理**：避免同时执行过多任务
3. **定期清理**：及时清除已完成的任务

### 🛡️ 错误处理
1. **任务失败**：查看详细错误信息，修正配置后重新添加
2. **队列卡住**：停止队列后重新启动
3. **数据备份**：定期导出重要的生成结果

## 注意事项

### ⚠️ 使用限制
- 正在执行的任务无法删除
- 队列停止时不会中断当前任务
- 任务执行依赖LLM配置

### 💡 提示
- 每个任务使用应用当前的LLM配置
- 任务名称自动生成，包含时间戳
- 所有生成结果可在数据库管理页面查看
- 支持实时监控任务执行进度

## 未来扩展

### 🚀 计划功能
- [ ] 任务模板保存和复用
- [ ] 定时任务调度
- [ ] 任务执行报告
- [ ] 任务依赖关系
- [ ] 分布式队列支持

---

*最后更新：2025年1月* 🎉 **任务队列功能已完成！享受自动化剧情生成的便利吧！** 