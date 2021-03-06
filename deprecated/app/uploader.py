#© 2020 By The Rector And Visitors Of The University Of Virginia

#Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
import flask, requests, time, json, os, warnings, re
from datetime import datetime
import pandas as pd
from flask import request
from flask import send_file
from auth import *
from minio_funcs import *
from metadata import *
from util import *
import copy


app = flask.Flask(__name__)

ROOT_DIR = os.environ.get("ROOT_DIR", "")
ORS_MDS = os.environ.get("ORS_URL", "http://localhost:80/")
MINIO_URL = os.environ.get("MINIO_URL", "localhost:9000")
MINIO_SECRET = os.environ.get("MINIO_SECRET")
MINIO_KEY = os.environ.get("MINIO_KEY")
EVI_PREFIX = 'evi:'

app.url_map.converters['everything'] = EverythingConverter


@app.route('/')
#@token_redirect
def homepage():
    return flask.render_template('upload_boot.html')


@app.route('/bucket/<bucketName>',methods = ['POST', 'DELETE'])
@token_required
def bucket(bucketName):

    if len(bucketName) < 3:
        return flask.jsonify({'created':False,
                        'error':"Bucket does not exist"}),400


    # get auth token from header
    #user_token = request.headers.get("Authorization").strip("Bearer ")

    # check the ability of a user to delete the bucket
    #resource = "transfer:bucket:" + bucketName

    if flask.request.method == 'POST':

        # check the ability of a user to create a bucket in the transfer service
        # by looking up permissions in the auth service
        #allowed = check_permission(user_token, "transfer", "transfer:createBucket")

        # if not allowed:
        #     return flask.Response(
        #         response = json.dumps({"error": "User is not allowed to create a Bucket"}),
        #         status_code = 403
        #         )


        if bucket_exists(bucketName):
            return flask.Response(
                response = json.dumps({
                    "@id": bucketName,
                    'error':"Bucket Already Exists"
                }),
                status_code = 400
                )

        success, error = make_bucket(bucketName)

        if not success:
            error_response = { "@id": resource_name, "message": "Failed to create bucket", "error": error}
            return flask.Response(json.dumps(error_response), status_code = 500)

        # resource_registration = register_resource(resource, user_token)
        #
        # if resource_registration.status_code != 200:
        #     return flask.Response(
        #         response= json.dumps({
        #             "@id": resource,
        #             "error": "Failed to register resource with auth server"
        #         }),
        #         status_code= 500
        #         )

        return jsonify({'created':True}),200

    if flask.request.method == 'DELETE':

        #allowed = check_permission(user_token, resource, "transfer:deleteBucket")
        #
        # if not allowed:
        #     return flask.jsonify({"error": "User lacks permission to delete resource"}), 403

        success, error = delete_bucket(bucketName)

        if not success:
            return flask.Response(
                response = json.dumps({
                    "@id": bucketName,
                    "message": "Failed to Delete Bucket",
                    "error": error
                }),
                status_code = 400
                )

        #resource_response = delete_resource(user_token, resource_name)
        return flask.Response(response=json.dumps({'deleted':True}))

@app.route('/data',methods = ['POST'])
@token_required
def just_upload():
    auth_header = request.headers.get("Authorization")
    if flask.request.method == 'POST':

        accept = request.headers.getlist('accept')
        #
        # if len(accept) > 0:
        #     accept = accept[0]


        if 'metadata' not in request.files.keys():

            error = "Missing Metadata File. Must pass in file with name metadata"

            return flask.jsonify({'uploaded':False,"Error":error}),400

        if 'files' not in request.files.keys() and 'data-file' not in request.files.keys():

            error = "Missing Data Files. Must pass in at least one file with name files"

            return flask.jsonify({'uploaded':False,"Error":error}),400

        if 'sha256' not in request.files.keys():

            error = "Missing Hash Value. Must pass in sha256 hash"
            print(request.files['sha256'])
            return flask.jsonify({'uploaded':False,"Error":error}),400

        files, meta, folder = getUserInputs(request.files,request.form)

        if 'bucket' in meta.keys():

            bucket = meta['bucket']

        else:

            bucket = 'breakfast'

        valid, error = validate_inputs(files,meta)

        if not valid:

            return flask.jsonify({'uploaded':False,"Error":error}),400

        ARK_NS = '99999'
        if 'namespace' in meta.keys():
            ARK_NS = meta['namespace']
            if not valid_namespace(ARK_NS):
                return flask.jsonify({'uploaded':False,"Error":'Invalid Namespace'}),400

        qualifier = False
        if 'qualifier' in meta.keys():
            qualifier = meta['qualifier']


        upload_failures = []
        minted_ids = []
        failed_to_mint = []

        least_one = False
        full_upload = False

        for file in files:

            start_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

            orginal_file_name = file.filename.split('/')[-1]

            file_type = orginal_file_name.split('.')[-1]

            current_id = mint_identifier(meta, ARK_NS, qualifier,auth_header)

            if current_id == 'error':

                if 'text/html' in accept:

                    return flask.render_template('failure.html')

                return flask.jsonify({'error':'Failed to mint Identifier'}),400


            file_data = file

            file_name = current_id.split('/')[1] + '.' + file_type


            sha256_hash = get_sha256(file)

            # if sha256_hash !=

            #result = upload(file,file_name ,bucket,folder)
            result = upload(file,orginal_file_name ,bucket,folder)

            success = result['upload']


            if success:
                obj_hash = get_obj_hash(orginal_file_name,bucket,folder)


                end_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

                location = result['location']

                activity_meta = {
                    "@type":EVI_PREFIX + "Activity",
                    "dateStarted":start_time,
                    "dateEnded":end_time,
                    EVI_PREFIX + "usedSoftware":"Transfer Service",
                    EVI_PREFIX + 'usedDataset':file_name,

                }

                act_id = mint_identifier(activity_meta, ARK_NS, qualifier,auth_header)

                activity_meta['@id'] = activity_meta

                file_meta = meta

                if EVI_PREFIX + 'generatedBy' not in file_meta.keys() and 'eg:generatedBy' not in file_meta.keys():
                    file_meta[EVI_PREFIX + 'generatedBy'] = activity_meta

                file_meta['distribution'] = []

                f = file_data
                f.seek(0, os.SEEK_END)
                size = f.tell()

                hash = {"@type": "PropertyValue", "name":"md5", "value": obj_hash}
                hash_id = mint_identifier(hash, ARK_NS, qualifier,auth_header)
                hash['@id'] = hash_id

                hash2 = {"@type": "PropertyValue", "name":"sha256", "value": sha256_hash}
                hash_id2 = mint_identifier(hash2, ARK_NS, qualifier,auth_header)
                hash2['@id'] = hash_id2

                file_meta['distribution'].append({
                    "@type":"DataDownload",
                    "name":orginal_file_name,
                    "fileFormat":file_name.split('.')[-1],
                    "contentSize":size,
                    "contentUrl":MINIO_URL + '/' + location,
                    "identifier":[hash,hash2]
                })

                download_id = mint_identifier(file_meta['distribution'][0], ARK_NS, qualifier,auth_header)

                file_meta['distribution'][0]['@id'] = download_id

                r = requests.put(ORS_URL + current_id,headers = {"Authorization": auth_header},
                            data=json.dumps({'distribution':file_meta['distribution']}))

                print('Hello below put call')
                print(r.content.decode())

                #Base meta taken from user

                if current_id != 'error':

                    least_one = True
                    minted_id = current_id
                    file_meta['@id'] = minted_id
                    minted_ids.append(minted_id)

                    print("Adding distribution to: " + str(minted_id))
                    if EVI_PREFIX + 'generatedBy' not in file_meta.keys() and 'eg:generatedBy' not in file_meta.keys():
                        r = requests.put(ORS_URL + minted_id,headers={"Authorization": auth_header},
                                    data=json.dumps({EVI_PREFIX + 'generatedBy':act_id,
                                    'distribution':file_meta['distribution']}))
                    else:
                        r = requests.put(ORS_URL + minted_id,headers={"Authorization": auth_header},
                                    data=json.dumps({'distribution':file_meta['distribution']}))

                else:


                    failed_to_mint.append(file.filename)

            else:

                r = requests.delete(
                        ORS_URL + minted_id,
                        headers={"Authorization": auth_header}
                        )

                upload_failures.append(file.filename)

        if len(upload_failures) == 0:

            full_upload = True

        if least_one:

            if len(minted_ids) > 0:

                minted_id = current_id

                if 'text/html' in accept:

                    return render_template('success.html',id = minted_id)

                return flask.jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200

            else:

                return flask.jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200
        if 'text/html' in accept:

            return flask.render_template('failure.html')

        return flask.jsonify({'error':'Files failed to upload.'}),400

@app.route('/data/<everything:ark>',methods = ['POST','GET','DELETE','PUT'])
@token_required
def all(ark):

    auth_header = request.headers.get("Authorization")
    #auth_token = access_header.strip("Bearer ")

    if flask.request.method == 'GET':

        accept = gather_accepted(request.headers.getlist('accept'))

        #ark = request.args.get('ark')

        print(ark)

        if not valid_ark(ark):
            return flask.jsonify({"error":"Improperly formatted Identifier"}), 400

        r = requests.get(
                ORS_MDS + ark,
                headers = {"Authorization": auth_header}
            )

        metareturned = r.json()

        if 'error' in metareturned.keys():
            return flask.jsonify({'error':"Identifier does not exist"}), 400

        location = get_file(metareturned['distribution'])

        if location is None:

            return  flask.jsonify({'error':"Given Identifier has no distribution in this framework"}), 400

        filename = location.split('/')[-1]

        result = send_file(ROOT_DIR + '/app/' + filename)

        os.remove(ROOT_DIR + '/app/' + filename)

        return result

    if flask.request.method == 'POST':

        accept = request.headers.getlist('accept')
        #
        # if len(accept) > 0:
        #     accept = accept[0]


        if 'metadata' not in request.files.keys():

            error = "Missing Metadata File. Must pass in file with name metadata"

            return flask.jsonify({'uploaded':False,"Error":error}),400

        if 'files' not in request.files.keys() and 'data-file' not in request.files.keys():

            error = "Missing Data Files. Must pass in at least one file with name files"

            return flask.jsonify({'uploaded':False,"Error":error}),400

        # if 'sha256' not in request.files.keys() and 'data-file' not in request.files.keys():
        #
        #     error = "Missing Hash Value. Must pass in sha256 file hash"
        #
        #     return flask.jsonify({'uploaded':False,"Error":error}),400

        files, meta, folder = getUserInputs(request.files,request.form)

        if 'bucket' in meta.keys():

            bucket = meta['bucket']

        else:

            bucket = 'breakfast'

        valid, error = validate_inputs(files,meta)

        if not valid:

            return flask.jsonify({'uploaded':False,"Error":error}),400

        ARK_NS = '99999'
        if 'namespace' in meta.keys():
            ARK_NS = meta['namespace']
            if not valid_namespace(ARK_NS):
                return flask.jsonify({'uploaded':False,"Error":'Invalid Namespace'}),400

        qualifier = False
        if 'qualifier' in meta.keys():
            qualifier = meta['qualifier']


        upload_failures = []
        minted_ids = []
        failed_to_mint = []

        least_one = False
        full_upload = False

        for file in files:

            start_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

            orginal_file_name = file.filename.split('/')[-1]

            file_type = orginal_file_name.split('.')[-1]

            current_id = mint_identifier(meta, ARK_NS, qualifier,auth_header)

            if current_id == 'error':

                if 'text/html' in accept:

                    return flask.render_template('failure.html')

                return flask.jsonify({'error':'Failed to mint Identifier'}),400


            file_data = file

            file_name = current_id.split('/')[1] + '.' + file_type

            #result = upload(file,file_name ,bucket,folder)
            result = upload(file,orginal_file_name ,bucket,folder)

            success = result['upload']


            if success:
                print('object uploaded')
                obj_hash = get_obj_hash(orginal_file_name,bucket,folder)
                new_hash = get_sha256(file_data)

                end_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

                location = result['location']

                activity_meta = {
                    "@type":EVI_PREFIX + "Activity",
                    "dateStarted":start_time,
                    "dateEnded":end_time,
                    EVI_PREFIX + "usedSoftware":"Transfer Service",
                    EVI_PREFIX + 'usedDataset':file_name,

                }

                act_id = mint_identifier(activity_meta, ARK_NS, qualifier,auth_header)

                activity_meta['@id'] = activity_meta

                file_meta = meta

                if EVI_PREFIX + 'generatedBy' not in file_meta.keys() and 'eg:generatedBy' not in file_meta.keys():
                    file_meta[EVI_PREFIX + 'generatedBy'] = activity_meta

                file_meta['distribution'] = []

                f = file_data
                f.seek(0, os.SEEK_END)
                size = f.tell()

                hash = {"@type": "PropertyValue", "name":"md5", "value": obj_hash}
                hash_id = mint_identifier(hash, ARK_NS, qualifier,auth_header)
                hash['@id'] = hash_id

                hash2 = {"@type": "PropertyValue", "name":"sha256", "value": new_hash}
                hash_id2 = mint_identifier(hash2, ARK_NS, qualifier,auth_header)
                hash2['@id'] = hash_id2

                file_meta['distribution'].append({
                    "@type":"DataDownload",
                    "name":orginal_file_name,
                    "fileFormat":file_name.split('.')[-1],
                    "contentSize":size,
                    "contentUrl":MINIO_URL + '/' + location,
                    "identifier":[hash,hash2]
                })

                download_id = mint_identifier(file_meta['distribution'][0], ARK_NS, qualifier,auth_header)

                file_meta['distribution'][0]['@id'] = download_id

                r = requests.put(ORS_URL + current_id,headers = {"Authorization": auth_header},
                            data=json.dumps({'distribution':file_meta['distribution']}))

                print('Hello below put call')
                print(r.content.decode())

                #Base meta taken from user

                if current_id != 'error':

                    least_one = True
                    minted_id = current_id
                    file_meta['@id'] = minted_id
                    minted_ids.append(minted_id)

                    print("Adding distribution to: " + str(minted_id))
                    if EVI_PREFIX + 'generatedBy' not in file_meta.keys() and 'eg:generatedBy' not in file_meta.keys():
                        r = requests.put(ORS_URL + minted_id,headers={"Authorization": auth_header},
                                    data=json.dumps({EVI_PREFIX + 'generatedBy':act_id,
                                    'distribution':file_meta['distribution']}))
                    else:
                        r = requests.put(ORS_URL + minted_id,headers={"Authorization": auth_header},
                                    data=json.dumps({'distribution':file_meta['distribution']}))

                else:


                    failed_to_mint.append(file.filename)

            else:

                r = requests.delete(
                        ORS_URL + minted_id,
                        headers={"Authorization": auth_header}
                        )

                upload_failures.append(file.filename)

        if len(upload_failures) == 0:

            full_upload = True

        if least_one:

            if len(minted_ids) > 0:

                minted_id = current_id

                if 'text/html' in accept:

                    return render_template('success.html',id = minted_id)

                return flask.jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200

            else:

                return flask.jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200
        if 'text/html' in accept:

            return flask.render_template('failure.html')

        return flask.jsonify({'error':'Files failed to upload.'}),400

    if flask.request.method == 'PUT':

        accept = gather_accepted(request.headers.getlist('accept'))

        if not valid_ark(ark):

            return jsonify({"error":"Improperly formatted Identifier"}),400

        r = requests.get(
                ORS_URL + ark,
                headers={"Authorization": auth_header}
                )

        meta = r.json()


        if 'files' not in request.files.keys() and 'data-file' not in request.files.keys():

            error = "Missing Data Files. Must pass in at least one file with name files"

            return jsonify({'uploaded':False,"Error":error}),400

        files = request.files.getlist('files')

        if 'bucket' in meta.keys():
            bucket = meta['bucket']
        else:
            bucket = 'breakfast'
        if 'folder' in meta.keys():
            folder = meta['folder']
        else:
            folder = ''

        ARK_NS = '99999'
        if 'namespace' in meta.keys():
            ARK_NS = meta['namespace']
        qualifier = False
        if 'qualifier' in meta.keys():
            qualifier = meta['qualifier']

        valid, error = validate_inputs(files,meta)

        if not valid:

            return jsonify({'uploaded':False,"Error":error}),400

        if 'version' in meta.keys():
            meta['version'] = meta['version'] + 1
        else:
            meta['version'] = 2.0

        meta['isBasedOn'] = ark

        if 'eg:evidenceGraph' in meta.keys():

            del meta['eg:evidenceGraph']

        upload_failures = []
        minted_ids = []
        failed_to_mint = []

        least_one = False
        full_upload = False

        for file in files:

            start_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

            file_name = file.filename.split('/')[-1]

            current_id = mint_identifier(meta, ARK_NS, qualifier,auth_header)


            file_data = file

            file_name = current_id.split('/')[1]

            result = upload(file,file_name,bucket,folder)

            success = result['upload']


            if success:

                obj_hash = get_obj_hash(file_name,bucket,folder)


                end_time = datetime.fromtimestamp(time.time()).strftime("%A, %B %d, %Y %I:%M:%S")

                location = result['location']

                activity_meta = {
                    "@type":"eg:Activity",
                    "dateStarted":start_time,
                    "dateEnded":end_time,
                    "eg:usedSoftware":"Transfer Service",
                    'eg:usedDataset':file_name,
                    "identifier":[{"@type": "PropertyValue", "name": "md5", "value": obj_hash}]
                }

                act_id = mint_identifier(activity_meta, ARK_NS, qualifier,auth_header)


                file_meta = meta

                file_meta['eg:generatedBy'] = act_id

                file_meta['distribution'] = []

                f = file_data
                f.seek(0, os.SEEK_END)
                size = f.tell()

                file_meta['distribution'].append({
                    "@type":"DataDownload",
                    "name":file_name,
                    "fileFormat":file_name.split('.')[-1],
                    "contentSize":size,
                    "contentUrl":'minionas.uvadcos.io/' + location
                })

                download_id = mint_identifier(file_meta['distribution'][0],ARK_NS, qualifier, auth_header)


                file_meta['distribution'][0]['@id'] = download_id

                #Base meta taken from user

                if current_id != 'error':

                    least_one = True

                    minted_id = current_id

                    file_meta['@id'] = minted_id

                    minted_ids.append(minted_id)

                    create_named_graph(file_meta,minted_id)

                    eg = make_eg(minted_id)

                    r = requests.put(
                            ORS_URL + minted_id,
                            data=json.dumps({
                                'eg:evidenceGraph':eg,
                                'eg:generatedBy':activity_meta,
                                'distribution':file_meta['distribution']
                                }),
                            headers={"Authorization": auth_header}
                            )

                else:

                    failed_to_mint.append(file.filename)

            else:

                upload_failures.append(file.filename)

        if len(upload_failures) == 0:

            full_upload = True

        if least_one:

            if len(minted_ids) > 0:

                minted_id = current_id

                if 'text/html' in accept:

                    return render_template('success.html',id = minted_id)

                return jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200

            else:

                return jsonify({'All files uploaded':full_upload,
                                'failed to upload':upload_failures,
                                'Minted Identifiers':minted_ids,
                                'Failed to mint Id for':failed_to_mint
                                }),200
        if 'text/html' in accept:

            return render_template('failure.html')

        return jsonify({'error':'Files failed to upload.'}),400

    if flask.request.method == 'DELETE':

        if valid_ark(ark):

            req = requests.get(
                    ORS_URL + ark,
                    headers={"Authorization": auth_header}
                    )

            if regestiredID(req.json()):

                meta = req.json()

            else:

                return flask.jsonify({"error":"Given Identifier not regesited"}),400

        else:
            return flask.jsonify({"error":"Improperly formatted Identifier"}),400

        if 'distribution' in meta.keys():
            if isinstance(meta['distribution'],list):
                if 'contentUrl' in meta['distribution'][0].keys():

                    minioLocation = meta['distribution'][0]['contentUrl']

                else:
                    return flask.jsonify({'deleted':False,'error':"Metadata distribution Improperly formatted"}),400
            else:
                return flask.jsonify({'deleted':False,'error':"Metadata distribution Improperly formatted"}),400
        else:
            return flask.jsonify({'deleted':False,'error':"Metadata distribution Improperly formatted"}),400

        bucket = minioLocation.split('/')[1]

        location = '/'.join(minioLocation.split('/')[2:])

        success, error = remove_file(bucket,location)

        if success:

            return flask.jsonify({'deleted':True}),200

        else:

            return flask.jsonify({'deleted':False,'error':error}),400


@app.route('/download/',methods = ['GET'])
@token_required
def download_html():
    return flask.render_template('download_homepage.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5002)
