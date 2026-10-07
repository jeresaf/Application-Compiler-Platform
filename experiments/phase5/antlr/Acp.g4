grammar Acp;
document: ('module' STRING ';' ('import' STRING ';')*)? 'application' object ';' declaration* EOF;
declaration: 'export'? ID STRING '@' INT object ';';
value: object | array | STRING | INT | 'true' | 'false' | 'null'
     | 'ref' STRING '@' INT
     | 'Money' STRING 'precision' INT 'scale' INT 'rounding' STRING;
object: '{' (STRING ':' value (',' STRING ':' value)*)? '}';
array: '[' (value (',' value)*)? ']';
ID: [a-zA-Z_] [a-zA-Z_0-9]*;
INT: '-'? ('0' | [1-9] [0-9]*);
STRING: '"' ('\\' (["\\/bfnrt] | 'u' HEX HEX HEX HEX) | ~["\\\r\n])* '"';
fragment HEX: [0-9a-fA-F];
WS: [ \t\r\n]+ -> skip;
