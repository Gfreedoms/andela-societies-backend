"""Contain utility functions and constants."""
import os
import requests
from collections import namedtuple
from flask import Response, current_app, jsonify, request, url_for

from api.models import Center, Role
from api.utils.marshmallow_schemas import basic_info_schema, redemption_schema


PaginatedResult = namedtuple(
    'PaginatedResult',
    ['data', 'count', 'page', 'pages', 'previous_url', 'next_url']
)


def paginate_items(fetched_data, serialize=True):
    """Paginate all roles for display."""
    from api.endpoints.redemption_requests import RedemptionRequest
    _page = request.args.get('page', type=int) or \
        current_app.config['DEFAULT_PAGE']
    _limit = request.args.get('limit', type=int) or \
        current_app.config['PAGE_LIMIT']
    page = current_app.config['DEFAULT_PAGE'] if _page < 0 else _page
    limit = current_app.config['PAGE_LIMIT'] if _limit < 0 else _limit

    fetched_data = fetched_data.paginate(
        page=page,
        per_page=limit,
        error_out=False
    )
    if fetched_data.items:
        previous_url = None
        next_url = None

        if fetched_data.has_next:
            next_url = url_for(request.endpoint, limit=limit,
                               page=page+1, _external=True)
        if fetched_data.has_prev:
            previous_url = url_for(request.endpoint, limit=limit,
                                   page=page-1, _external=True)

        if serialize:
            data_list = []
            for _fetched_item in fetched_data.items:
                if isinstance(_fetched_item, RedemptionRequest):
                    data_item = serialize_redmp(_fetched_item)
                    data_list.append(data_item)
                else:
                    data_item = _fetched_item.serialize()
                    data_list.append(data_item)
        else:
            data_list = fetched_data.items

            return PaginatedResult(
                data_list, fetched_data.total, fetched_data.page,
                fetched_data.pages, previous_url, next_url
            )

        return response_builder(dict(
            status="success",
            data=data_list,
            count=fetched_data.total,
            pages=fetched_data.pages,
            nextUrl=next_url,
            previousUrl=previous_url,
            currentPage=fetched_data.page,
            message="fetched successfully."
        ), 200)

    if not serialize:
        return PaginatedResult(
            [], 0, None, 0, None, None
        )

    return response_builder(dict(
        status="success",
        data=dict(data_list=[],
                  count=0),
        message="Resources were not found."
    ), 404)


def edit_role(payload, search_term):
    """Find and edit the role."""
    role = Role.query.get(search_term)
    # if edit request == stored value
    if not role:
        return response_builder(dict(status="fail",
                                     message="Role does not exist."), 404)

    try:
        if payload["name"] == role.name:
            return response_builder(dict(
                data=dict(path=role.serialize()),
                message="No change specified."
            ), 200)

        else:
            old_role_name = role.name
            role.name = payload["name"]
            role.save()

            return response_builder(dict(
                data=dict(path=role.serialize()),
                message="Role {} has been changed"
                        " to {}.".format(old_role_name, role.name)
            ), 200)

    except KeyError:
        return response_builder(
            dict(status="fail",
                 message="Name to edit to must be provided."), 400)


def find_item(data):
    """Build the response with found/404 item in DB."""
    from api.endpoints.redemption_requests import RedemptionRequest
    if data:

        # Serialization of RedemptionRequest
        if isinstance(data, RedemptionRequest):
            return response_builder(dict(
                data=serialize_redmp(data),
                status="success",
                message="{} fetched successfully.".format(data.name)
            ), 200)

        return response_builder(dict(
            data=data.serialize(),
            status="success",
            message="{} fetched successfully.".format(data.name)
        ), 200)

    return response_builder(dict(
        data=None,
        status="fail",
        message="Resource does not exist."
    ), 404)


def response_builder(data, status_code=200):
    """Build the jsonified response to return."""
    response = jsonify(data)
    response.status_code = status_code
    return response


def add_extra_user_info(
    token,
    user_id,
    url=os.environ.get('ANDELA_API_URL')
):  # pragma: no cover
    """Retrive user information from ANDELA API.

    params:
        token(str): valid jwt token
        user_id(str): id for user to retive information about

    Return:
        tuple(location, cohort, api_response)
    """
    cohort = location = None
    Bearer = 'Bearer '
    headers = {'Authorization': Bearer + token}

    try:
        api_response = requests.get(url + f"users/{user_id}", headers=headers)
    except requests.exceptions.ConnectionError:
        response = Response()
        response.status_code = 503
        response.json = lambda: {"Error": "Network Error."}
        return cohort, location, response
    except Exception:
        response = Response()
        response.status_code = 500
        response.json = lambda: {"Error": "Something went wrong."}
        return cohort, location, response

    if api_response.status_code == 200 and api_response.json().get('cohort'):
        from api.endpoints.cohorts.models import Cohort
        cohort = Cohort.query.filter_by(
            uuid=api_response.json().get('cohort').get('id')).first()
        if not cohort:
            cohort = Cohort(uuid=api_response.json().get('cohort').get('id'),
                            name=api_response.json().get('cohort').get('name'))

        location = Center.query.filter_by(
            uuid=api_response.json().get('location').get('id')).first()
        if not location:
            location = Center(
                uuid=api_response.json().get('location').get('id'))
    return cohort, location, api_response


def serialize_redmp(redemption):
    """To serialize and package redeptions."""
    serial_data, _ = redemption_schema.dump(redemption)
    seriallized_user, _ = basic_info_schema.dump(redemption.user)
    serilaized_society, _ = basic_info_schema.dump(redemption.user.society)
    serial_data["user"] = seriallized_user
    serial_data["society"] = serilaized_society
    serial_data["center"], _ = basic_info_schema.dump(redemption.center)
    return serial_data
