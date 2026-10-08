"""Closed typed Java contracts. Stable origins determine names, never behavior.

Readers preserve absence separately from explicit null, reject unknown members,
and validate exact semantic types before an operation enters a transaction.
"""
import hashlib
import json
from model import CapabilityError, identifier


def quoted(value):
    return json.dumps(value, ensure_ascii=True)


def name(origin):
    return identifier(origin, 'T')


def member(origin):
    return identifier(origin, 'v')


class Contracts:
    def __init__(self, nodes):
        self.nodes = {n['id']: n for n in nodes}
        self.money = {}

    def fields(self, owner):
        return sorted((n for n in self.nodes.values() if n['kind'] == 'Field' and n['data']['owner']['id'] == owner), key=lambda n: n['id'])

    def type(self, t):
        k = t['kind']
        if k == 'Nullable':
            return self.type(t['item'])
        if k in ('Value', 'Named'):
            return name(t['definition']['id'])
        if k == 'Identifier':
            return name(t['entity']['id']) + 'Id'
        if k in ('Money', 'Decimal', 'Percentage'):
            key = 'D' + hashlib.sha256(json.dumps(t, sort_keys=True).encode()).hexdigest()[:24]
            self.money[key] = t
            return key
        simple = {'String': 'String', 'Boolean': 'Boolean'}
        if k not in simple:
            raise CapabilityError('JAVA_TYPE:' + k)
        return simple[k]

    def read(self, t, value):
        k = t['kind']
        if k == 'Nullable':
            return f'({value}.isNull() ? null : {self.read(t["item"], value)})'
        if k in ('Value', 'Named'):
            return f'{self.type(t)}.read({value})'
        if k == 'Identifier':
            return f'new {self.type(t)}(text({value}))'
        if k in ('Money', 'Decimal', 'Percentage'):
            return f'new {self.type(t)}(decimal({value}))'
        if k == 'String':
            return f'text({value})'
        if k == 'Boolean':
            return f'bool({value})'
        if k in ('Integer', 'Duration'):
            return f'integer({value})'
        if k == 'Date':
            return f'java.time.LocalDate.parse(text({value}))'
        if k == 'Instant':
            return f'java.time.Instant.parse(text({value}))'
        raise CapabilityError('JAVA_READER:' + k)

    def field_type(self, f):
        t = self.type(f['data']['type'])
        return 'Slot<' + t + '>' if f['data']['optional'] else t

    def construct(self, owner, bindings, expression):
        by_field = {b['field']['id']: b['value'] for b in bindings}
        args = []
        for f in self.fields(owner):
            if f['id'] not in by_field:
                if not f['data']['optional']:
                    raise CapabilityError('MISSING_BINDING:' + f['id'])
                args.append('Slot.absent()')
            else:
                value = expression(by_field[f['id']])
                args.append('Slot.of(' + value + ')' if f['data']['optional'] else value)
        return f'new {name(owner)}(' + ', '.join(args) + ')'

    def record(self, owner, fields=None):
        fields = self.fields(owner) if fields is None else fields
        typ = name(owner)
        arguments = ', '.join(f'@JsonProperty({quoted(f["id"])}) {self.field_type(f)} {member(f["id"])}' for f in fields)
        checks, readers, serializer = [], [], []
        for f in fields:
            d, key = f['data'], quoted(f['id'])
            var = member(f['id'])
            if d['optional'] or d['type']['kind'] != 'Nullable':
                checks.append(f'java.util.Objects.requireNonNull({var}, {key});')
            base = d['type']['item'] if d['type']['kind'] == 'Nullable' else d['type']
            if base['kind'] == 'String':
                value = var + '.value()' if d['optional'] else var
                checks.append(f'if ({value} != null) validText({value});')
            if d['optional']:
                readers.append(f'(n.has({key}) ? Slot.of({self.read(d["type"], "n.get(" + key + ")")}) : Slot.absent())')
                serializer.append(f'if ({var}.present()) g.writeObjectField({key}, {var}.value());')
                if d['type']['kind'] != 'Nullable':
                    checks.append(f'if ({var}.present()) java.util.Objects.requireNonNull({var}.value(), {key});')
            else:
                checks.insert(0, '')
                readers.append(self.read(d['type'], 'required(n, ' + key + ')'))
                serializer.append(f'g.writeObjectField({key}, {var});')
        allowed = ', '.join(quoted(f['id']) for f in fields)
        return f'''
    @JsonDeserialize(using={typ}.Reader.class)
    @JsonSerialize(using={typ}.Writer.class)
    public record {typ}({arguments}) {{
        public {typ} {{ {' '.join(checks)} }}
        public static {typ} read(JsonNode n) {{
            shape(n, java.util.Set.of({allowed}));
            return new {typ}({', '.join(readers)});
        }}
        public static final class Reader extends JsonDeserializer<{typ}> {{
            @Override public {typ} deserialize(JsonParser p, DeserializationContext c) throws java.io.IOException {{
                try {{ return read(p.getCodec().readTree(p)); }}
                catch (RuntimeException e) {{ throw JsonMappingException.from(p, "SEMANTIC_INPUT", e); }}
            }}
        }}
        public static final class Writer extends JsonSerializer<{typ}> {{
            @Override public void serialize({typ} value, JsonGenerator g, SerializerProvider p) throws java.io.IOException {{
                value.write(g);
            }}
        }}
        private void write(JsonGenerator g) throws java.io.IOException {{
            g.writeStartObject(); {' '.join(serializer)} g.writeEndObject();
        }}
    }}
'''

    def source(self):
        pieces = []
        for n in sorted(self.nodes.values(), key=lambda n: n['id']):
            k, id = n['kind'], n['id']
            if k in ('Entity', 'ValueObject'):
                pieces.append(self.record(id))
                if k == 'Entity':
                    t = name(id) + 'Id'
                    pieces.append(f'public record {t}(@JsonValue String value) {{ @JsonCreator(mode=JsonCreator.Mode.DELEGATING) public {t} {{ validText(value); if (blankIdentity(value)) throw new IllegalArgumentException("EMPTY_IDENTITY"); }} }}')
            elif k == 'Event':
                pieces.append(self.record(id, [self.nodes[r['id']] for r in n['data']['payload']]))
            elif k == 'TypeDefinition':
                d = n['data']
                if d['base']['kind'] != 'String':
                    raise CapabilityError('JAVA_NOMINAL_BASE_CONSTRAINT:' + id)
                base = self.type(d['base']); v = 'value'
                check = ''
                refinement = d.get('refinement', {})
                if refinement.get('kind') == 'LENGTH' and d['base']['kind'] == 'String':
                    check = f'if (value.codePointCount(0,value.length()) < {refinement["min"]} || value.codePointCount(0,value.length()) > {refinement["max"]}) throw new IllegalArgumentException("REFINEMENT");'
                elif refinement and refinement.get('kind') != 'NONE':
                    raise CapabilityError('JAVA_REFINEMENT:' + id)
                unicode = 'validText(value);' if d['base']['kind'] == 'String' else ''
                pieces.append(f'public record {name(id)}(@JsonValue {base} value) {{ public {name(id)} {{ java.util.Objects.requireNonNull(value); {unicode} {check} }} public static {name(id)} read(JsonNode n) {{ return new {name(id)}({self.read(d["base"], "n")}); }} }}')
        for key, t in sorted(self.money.items()):
            currency = 'public String currency() { return ' + quoted(t['currency']) + '; }' if t['kind'] == 'Money' else ''
            pieces.append(f'''public record {key}(java.math.BigDecimal value) {{
                public {key} {{ java.util.Objects.requireNonNull(value); value = value.setScale({t['scale']}, java.math.RoundingMode.UNNECESSARY); if (value.precision() > {t['precision']}) throw new IllegalArgumentException("DECIMAL_PRECISION"); }}
                @JsonValue public String wire() {{ return value.toPlainString(); }} {currency}
            }}''')
        return '''package acp.generated;
import com.fasterxml.jackson.annotation.*;
import com.fasterxml.jackson.core.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.annotation.*;

/** Generated from exact semantic origins. No map-shaped operation contracts. */
public final class Contracts {
    private Contracts() {}
    public record Slot<T>(boolean present, T value) {
        public Slot { if (!present && value != null) throw new IllegalArgumentException("ABSENT_VALUE"); }
        public static <T> Slot<T> absent() { return new Slot<>(false, null); }
        public static <T> Slot<T> of(T value) { return new Slot<>(true, value); }
    }
    static void shape(JsonNode n, java.util.Set<String> allowed) {
        if (n == null || !n.isObject()) throw new IllegalArgumentException("OBJECT_REQUIRED");
        n.fieldNames().forEachRemaining(k -> { if (!allowed.contains(k)) throw new IllegalArgumentException("UNKNOWN_MEMBER"); });
    }
    static JsonNode required(JsonNode n, String key) { if (!n.has(key)) throw new IllegalArgumentException("REQUIRED_INPUT:" + key); return n.get(key); }
    static boolean blankIdentity(String s) { return s.codePoints().allMatch(cp -> Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85); }
    static void validText(String s) {
        java.util.Objects.requireNonNull(s);
        for (int i=0;i<s.length();i++) {
            char c=s.charAt(i);
            if (Character.isHighSurrogate(c)) { if (++i>=s.length() || !Character.isLowSurrogate(s.charAt(i))) throw new IllegalArgumentException("UNICODE_SCALAR"); }
            else if (Character.isLowSurrogate(c)) throw new IllegalArgumentException("UNICODE_SCALAR");
        }
    }
    static String text(JsonNode n) { if (n == null || !n.isTextual()) throw new IllegalArgumentException("STRING_REQUIRED"); String s=n.textValue(); validText(s); return s; }
    static Boolean bool(JsonNode n) { if (n == null || !n.isBoolean()) throw new IllegalArgumentException("BOOLEAN_REQUIRED"); return n.booleanValue(); }
    static java.math.BigDecimal decimal(JsonNode n) {
        String s=text(n);
        if (s.length()>128 || !s.matches("-?(0|[1-9][0-9]*)(\\\\.[0-9]+)?")) throw new IllegalArgumentException("DECIMAL_REPRESENTATION");
        return new java.math.BigDecimal(s);
    }
    static Long integer(JsonNode n) { if (n == null || !n.isIntegralNumber() || !n.canConvertToLong()) throw new IllegalArgumentException("INTEGER_REQUIRED"); return n.longValue(); }
''' + '\n'.join(pieces) + '\n}\n'
