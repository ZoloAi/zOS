**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Resolvers

**Resolvers** handle data and UI resolution, bridging zDispatch with zData and zLoader subsystems for data operations and UI block loading.

## Overview

| Resolver | Purpose | Subsystem |
|----------|---------|-----------|
| **DataResolver** | Data operations and queries | zData |
| **UIResolver** | UI block resolution from zUI files | zLoader |

---

## DataResolver

**Resolves data operations by routing to zData subsystem.**

### Purpose

Provide a clean interface between zDispatch and zData for database operations, query building, and data transformations.

### Operations

```python
from zOS import zOS

z = zOS()
resolver = DataResolver(z)

# Read single record
result = resolver.resolve_read({
    "model": "users",
    "where": {"id": 1}
})

# List multiple records
results = resolver.resolve_list({
    "model": "products",
    "where": {"category": "electronics"},
    "order_by": "price",
    "limit": 10
})

# Create record
result = resolver.resolve_create({
    "model": "orders",
    "values": {
        "user_id": 123,
        "total": 99.99,
        "status": "pending"
    }
})

# Update record
result = resolver.resolve_update({
    "model": "users",
    "values": {"status": "active"},
    "where": {"id": 1}
})

# Delete record
result = resolver.resolve_delete({
    "model": "users",
    "where": {"id": 1}
})
```

### Query Building

```python
class DataResolver:
    def build_query(self, query_data):
        """Build query from dict specification."""
        model = query_data.get("model")
        where = query_data.get("where", {})
        fields = query_data.get("fields", [])
        order_by = query_data.get("order_by")
        limit = query_data.get("limit")
        offset = query_data.get("offset")
        
        query = self.zos.data.query(model)
        
        if where:
            query = query.where(**where)
        
        if fields:
            query = query.select(*fields)
        
        if order_by:
            query = query.order_by(order_by)
        
        if limit:
            query = query.limit(limit)
        
        if offset:
            query = query.offset(offset)
        
        return query
```

### Examples

#### Simple Read

```python
# Read user by ID
data = {
    "model": "users",
    "where": {"id": 123}
}
user = resolver.resolve_read(data)
# Returns: {"id": 123, "name": "Alice", "email": "alice@example.com"}
```

#### Complex Query

```python
# List products with filters
data = {
    "model": "products",
    "where": {
        "category": "electronics",
        "price": {"$lt": 1000}
    },
    "fields": ["id", "name", "price"],
    "order_by": "price",
    "limit": 20,
    "offset": 0
}
products = resolver.resolve_list(data)
```

#### Batch Create

```python
# Create multiple records
data = {
    "model": "tags",
    "values": [
        {"name": "urgent"},
        {"name": "important"},
        {"name": "archived"}
    ]
}
tags = resolver.resolve_create_batch(data)
```

### Integration

```python
# In CommandLauncher
if KEY_ZREAD in horizontal:
    read_data = horizontal[KEY_ZREAD]
    return self.data_resolver.resolve_read(read_data)

if KEY_ZDATA in horizontal:
    data_command = horizontal[KEY_ZDATA]
    action = data_command.get(KEY_ACTION)
    
    if action == "read":
        return self.data_resolver.resolve_read(data_command)
    elif action == "list":
        return self.data_resolver.resolve_list(data_command)
    # ... etc
```

### Error Handling

```python
class DataResolver:
    def resolve_read(self, data):
        """Resolve read operation with error handling."""
        try:
            if "model" not in data:
                self.logger.error("Missing 'model' in read data")
                return None
            
            return self.zos.data.read(data)
        
        except Exception as e:
            self.logger.error(f"Data read failed: {e}")
            return None
```

### Context Passing

```python
# With context
context = {
    "user_id": 123,
    "session_id": "abc"
}

result = resolver.resolve_read(
    data={"model": "users", "where": {"id": 1}},
    context=context
)

# Resolver passes context to zData
# zData can use context for:
# - Row-level security
# - Audit logging
# - Tenant isolation
```

---

## UIResolver

**Resolves UI blocks from zUI files via zLoader subsystem.**

### Purpose

Load and resolve UI block definitions from `.zui` files, enabling declarative UI composition.

### Operations

```python
from zOS import zOS

z = zOS()
resolver = UIResolver(z)

# Load UI block from file
block = resolver.resolve_block(
    file_path="admin.zui",
    block_name="main_menu"
)

# Load with context
block = resolver.resolve_block(
    file_path="forms.zui",
    block_name="contact_form",
    context={"user_id": 123}
)
```

### Block Structure

```yaml
# admin.zui
main_menu:
  title: "Admin Panel"
  items:
    users:
      label: "Manage Users"
      zFunc: manage_users
    settings:
      label: "Settings"
      zFunc: edit_settings
    logout:
      label: "Logout"
      zLogout: true
```

### Resolution Logic

```python
class UIResolver:
    def resolve_block(self, file_path, block_name, context=None):
        """Load UI block from zUI file."""
        # Load file via zLoader
        ui_data = self.zos.loader.load_zui(file_path)
        
        if not ui_data:
            self.logger.error(f"Could not load {file_path}")
            return None
        
        # Extract block
        block = ui_data.get(block_name)
        
        if not block:
            self.logger.error(f"Block '{block_name}' not found in {file_path}")
            return None
        
        # Apply context substitutions
        if context:
            block = self._apply_context(block, context)
        
        return block
    
    def _apply_context(self, block, context):
        """Replace context variables in block."""
        # Example: {{user_id}} → context["user_id"]
        import json
        block_str = json.dumps(block)
        
        for key, value in context.items():
            block_str = block_str.replace(f"{{{{{key}}}}}", str(value))
        
        return json.loads(block_str)
```

### Examples

#### Menu Resolution

```python
# Load admin menu
menu = resolver.resolve_block(
    file_path="admin.zui",
    block_name="main_menu"
)

# Use with menu modifier
z.dispatch.handle("menu*", menu)
```

#### Form Resolution

```python
# Load contact form
form = resolver.resolve_block(
    file_path="forms.zui",
    block_name="contact_form"
)

# Display form
z.dispatch.handle("form", {"zDialog": form})
```

#### Context Substitution

```yaml
# profile.zui
edit_profile:
  title: "Edit Profile"
  fields:
    - name: user_id
      value: "{{user_id}}"
      hidden: true
    - name: email
      value: "{{email}}"
      type: email
```

```python
# Load with context
context = {"user_id": 123, "email": "alice@example.com"}
form = resolver.resolve_block(
    file_path="profile.zui",
    block_name="edit_profile",
    context=context
)

# Result has context values substituted
# form["fields"][0]["value"] = 123
# form["fields"][1]["value"] = "alice@example.com"
```

### Integration

```python
# In CommandLauncher
if KEY_ZVAFILE in context and KEY_ZBLOCK in context:
    file_path = context[KEY_ZVAFILE]
    block_name = context[KEY_ZBLOCK]
    
    block = self.ui_resolver.resolve_block(
        file_path=file_path,
        block_name=block_name,
        context=context
    )
    
    # Dispatch resolved block
    return self.launch(block, context=context, walker=walker)
```

### Caching

```python
class UIResolver:
    def __init__(self, zos):
        self.zos = zos
        self.cache = {}
    
    def resolve_block(self, file_path, block_name, context=None):
        """Load UI block with caching."""
        cache_key = f"{file_path}:{block_name}"
        
        # Check cache
        if cache_key in self.cache:
            block = self.cache[cache_key]
        else:
            # Load and cache
            block = self._load_block(file_path, block_name)
            if block:
                self.cache[cache_key] = block
        
        # Apply context (always fresh)
        if context and block:
            block = self._apply_context(block.copy(), context)
        
        return block
```

### Error Handling

```python
class UIResolver:
    def resolve_block(self, file_path, block_name, context=None):
        """Resolve block with error handling."""
        try:
            # Load file
            ui_data = self.zos.loader.load_zui(file_path)
            
            if not ui_data:
                self.logger.error(f"File not found: {file_path}")
                return None
            
            # Extract block
            if block_name not in ui_data:
                self.logger.error(
                    f"Block '{block_name}' not found in {file_path}. "
                    f"Available blocks: {list(ui_data.keys())}"
                )
                return None
            
            block = ui_data[block_name]
            
            # Apply context
            if context:
                block = self._apply_context(block, context)
            
            return block
        
        except Exception as e:
            self.logger.error(f"Block resolution failed: {e}")
            return None
```

---

## Resolver Integration Flow

```
Command with Data/UI Reference
    ↓
CommandLauncher.launch()
    ↓
[Detect Reference Type]
    ↓
├─ Data Operation
│   ├─ zRead → DataResolver.resolve_read()
│   ├─ zData → DataResolver.resolve_[action]()
│   └─ Auto-CRUD → DataResolver.resolve_crud()
│       ↓
│       zData Subsystem
│       ↓
│       Database
│
└─ UI Reference
    ├─ zVaFile + zBlock → UIResolver.resolve_block()
    └─ Context substitution
        ↓
        zLoader Subsystem
        ↓
        .zui File
        ↓
        Resolved Block
        ↓
        Dispatch Block Contents
```

---

## Best Practices

### DataResolver

```python
# ✅ Good: Use resolver for data operations
result = data_resolver.resolve_read({
    "model": "users",
    "where": {"id": 1}
})

# ❌ Bad: Direct zData calls bypass resolver
result = z.data.read(...)  # Loses resolver benefits
```

### UIResolver

```python
# ✅ Good: Use resolver for UI blocks
block = ui_resolver.resolve_block("admin.zui", "main_menu")

# ❌ Bad: Manual file loading
with open("admin.zui") as f:
    data = yaml.load(f)
    block = data["main_menu"]  # No caching, no context
```

### Context Passing

```python
# ✅ Good: Pass context for substitutions
block = resolver.resolve_block(
    "profile.zui",
    "edit_form",
    context={"user_id": 123}
)

# ❌ Bad: Missing context
block = resolver.resolve_block("profile.zui", "edit_form")
# {{user_id}} not substituted!
```

### Error Handling

```python
# ✅ Good: Check for None
block = resolver.resolve_block("admin.zui", "menu")
if block:
    z.dispatch.handle("menu*", block)
else:
    print("Failed to load menu")

# ❌ Bad: Assume success
block = resolver.resolve_block("admin.zui", "menu")
z.dispatch.handle("menu*", block)  # May crash if None
```

---

## Configuration

Resolvers use zConfig settings:

```python
# DataResolver
# - Uses zData configuration
# - Database connection from zConfig
# - Model definitions from zData

# UIResolver
# - Uses zLoader configuration
# - UI file paths from zConfig
# - Caching enabled/disabled via zConfig
```

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
