// Run locally once; the private key must never be committed.
package main

import (
 "crypto/ecdsa"
 "crypto/elliptic"
 "crypto/rand"
 "crypto/x509"
 "encoding/pem"
 "flag"
 "log"
 "os"
 "path/filepath"
)

func main() {
 private := flag.String("private", ".work/signing/release.pem", "private output (must not exist)")
 public := flag.String("public", "release/csqtt-public.pem", "public output")
 flag.Parse()
 if _, err := os.Stat(*private); !os.IsNotExist(err) { log.Fatal("private key path already exists") }
 key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader); if err != nil { log.Fatal(err) }
 secret, err := x509.MarshalPKCS8PrivateKey(key); if err != nil { log.Fatal(err) }
 pub, err := x509.MarshalPKIXPublicKey(&key.PublicKey); if err != nil { log.Fatal(err) }
 for _, path := range []string{*private,*public} { if err := os.MkdirAll(filepath.Dir(path),0700); err != nil { log.Fatal(err) } }
 f,err:=os.OpenFile(*private,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600);if err!=nil {log.Fatal(err)}
 if err=pem.Encode(f,&pem.Block{Type:"PRIVATE KEY",Bytes:secret});err!=nil{log.Fatal(err)};if err=f.Close();err!=nil{log.Fatal(err)}
 if err=os.WriteFile(*public,pem.EncodeToMemory(&pem.Block{Type:"PUBLIC KEY",Bytes:pub}),0644);err!=nil{log.Fatal(err)}
}
