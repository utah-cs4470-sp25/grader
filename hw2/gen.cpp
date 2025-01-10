#include <assert.h>
#include <stdio.h>

int main(void) {
  for (int i = 0; i <= 255; i++) {
    char fn[256];
    const char *dir = ((i >= 32 && i <= 126) && i != 34) ? "ok" : "error";
    sprintf(fn, "%s/print_%03d.jpl", dir, i);
    FILE *f = fopen(fn, "w");
    assert(f);
    fprintf(f, "print \"%c\"\n", i);
    fclose(f);
  }

  //for (int i = 0; i <= 255; i++) {
  //  char fn[256];
  //  const char *dir =
  //      ((i >= 'a' && i <= 'z') || (i >= 'A' && i <= 'Z')) ? "ok" : "error";
  //  sprintf(fn, "%s/variable_%03d.jpl", dir, i);
  //  FILE *f = fopen(fn, "w");
  //  assert(f);
  //  fprintf(f, "let %c = 7\n", i);
  //  fclose(f);
  //}

  for (int i = 40; i <= 128; i++) {
    if ((i >= 'a' && i <= 'z') || (i >= 'A' && i <= 'Z') || (i >= '0' && i <= '9') || (i == '_') || (i == '.')) {
      char fn[256];
      const char *dir = "ok";
      sprintf(fn, "%s/in_variable_%03d.jpl", dir, i);
      FILE *f = fopen(fn, "w");
      assert(f);
      fprintf(f, "let xx%cxx = 7\n", i);
      fclose(f);
    }
  }

  for (int i = 128; i <= 180; i++) {
    char fn[256];
    const char *dir = "error";
    sprintf(fn, "%s/in_variable_%03d.jpl", dir, i);
    FILE *f = fopen(fn, "w");
    assert(f);
    fprintf(f, "let xx%cxx = 7\n", i);
    fclose(f);
  }

  for (int i = 40; i <= 128; i++) {
    if ((i >= 'a' && i <= 'z') || (i >= 'A' && i <= 'Z') || (i >= '0' && i <= '9') || (i == '_') || (i == '.')) {
      char fn[256];
      const char *dir = "ok";
      sprintf(fn, "%s/in_comment_%03d.jpl", dir, i);
      FILE *f = fopen(fn, "w");
      assert(f);
      fprintf(f, "/* %c */", i);
      fclose(f);
    }
  }

  for (int i = 128; i <= 180; i++) {
    char fn[256];
    const char *dir = "error";
    sprintf(fn, "%s/in_comment_%03d.jpl", dir, i);
    FILE *f = fopen(fn, "w");
    assert(f);
    fprintf(f, "/* %c */", i);
    fclose(f);
  }

}
