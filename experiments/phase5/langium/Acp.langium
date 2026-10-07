grammar Acp
entry Document: 'application' header=RecordValue ';' declarations+=Declaration*;
Declaration: kind=ID name=STRING '@' revision=INT body=RecordValue ';';
Value: RecordValue | ListValue | Text | IntegerValue | BooleanValue | Null | Reference | Money;
RecordValue: '{' (pairs+=Pair (',' pairs+=Pair)*)? '}';
Pair: key=STRING ':' value=Value;
ListValue: '[' (values+=Value (',' values+=Value)*)? ']';
Text: value=STRING;
IntegerValue: value=INT;
BooleanValue: value=('true' | 'false');
Null: value='null';
Reference: 'ref' target=[Declaration:STRING] '@' revision=INT;
Money: 'Money' currency=STRING 'precision' precision=INT 'scale' scale=INT 'rounding' rounding=STRING;
hidden terminal WS: /\s+/;
terminal ID: /[a-zA-Z_][a-zA-Z_0-9]*/;
terminal INT returns number: /-?(0|[1-9][0-9]*)/;
terminal STRING: /"([^"\\\r\n]|\\(["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/;
