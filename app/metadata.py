#© 2020 By The Rector And Visitors Of The University Of Virginia

#Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import requests
import json
import os

ORS_URL = os.environ.get("ORS_URL", "http://localhost:80/")
MINIO_URL = os.environ.get("MINIO_URL", "localhost:9000")
MINIO_SECRET = os.environ.get("MINIO_SECRET")
MINIO_KEY = os.environ.get("MINIO_KEY")

def mint_identifier(meta,ARK_NS,qualifier = False,token=None):

    if qualifier:
        url = ORS_URL + 'ark:' + ARK_NS + '/' + qualifier + '/' + random_alphanumeric_string(30)
    else:
        url = ORS_URL + 'shoulder/ark:' + ARK_NS

    #Create Identifier for each file uploaded
    r = requests.post(
            url,
            data=json.dumps(meta),
            headers={"Authorization": token}
            )
    return r.json()['created']

def retrieve_metadata(ark,token):

    r = requests.get(
        ORS_URL + ark,
        headers={"Authorization": token}
        )

    return r.json()
