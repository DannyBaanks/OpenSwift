/* Token dump for the studio highlighter. Links MiniSwift's lexer (MIT). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <msf.h>

static char *read_all(size_t *out_len) {
    size_t cap = 4096, len = 0;
    char *buf = malloc(cap);
    if (!buf) return NULL;
    for (;;) {
        if (len + 2048 > cap) {
            cap *= 2;
            char *next = realloc(buf, cap);
            if (!next) { free(buf); return NULL; }
            buf = next;
        }
        size_t n = fread(buf + len, 1, 2048, stdin);
        len += n;
        if (n < 2048) break;
    }
    buf[len] = 0;
    *out_len = len;
    return buf;
}

int main(void) {
    size_t len = 0;
    char *text = read_all(&len);
    if (!text) return 1;
    Source src = { .data = text, .len = len, .filename = "studio.swift" };
    TokenStream ts;
    token_stream_init(&ts, 256);
    if (lexer_tokenize(&src, &ts, 0, NULL) != 0) {
        token_stream_free(&ts);
        free(text);
        return 1;
    }
    fputs("[", stdout);
    int first = 1;
    for (size_t i = 0; i < ts.count; i++) {
        Token t = ts.tokens[i];
        if (t.type == TOK_WHITESPACE || t.type == TOK_NEWLINE || t.type == TOK_EOF || t.len == 0)
            continue;
        const char *name = token_type_name(t.type);
        if (!first) fputc(',', stdout);
        first = 0;
        fprintf(stdout, "{\"type\":\"%s\",\"start\":%u,\"end\":%u}", name, t.pos, t.pos + t.len);
    }
    fputs("]\n", stdout);
    token_stream_free(&ts);
    free(text);
    return 0;
}
