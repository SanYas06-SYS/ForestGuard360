import pytest
from backend.areas import validate_area,contains

def test_local_area_interior_boundary_and_concavity():
    area=validate_area([[0,0],[0,2],[1,1],[2,2],[2,0],[0,0]])
    assert contains(area,.5,.5)
    assert contains(area,0,1)
    assert contains(area,1,1)
    assert not contains(area,1,1.8)
    assert not contains(area,3,3)
    assert not contains(None,0,0)

@pytest.mark.parametrize('area',[
    [],[[0,0],[1,1]],[[0,0],[1,1],[2,2]],
    [[0,0],[2,2],[0,2],[2,0]],[[0,0],[0,1],[0,0],[1,0]],
    [[True,0],[0,1],[1,0]],[[float('nan'),0],[0,1],[1,0]],
    [[91,0],[0,1],[1,0]],[[0,-179],[0,179],[1,179]],
])
def test_invalid_patrol_borders(area):
    with pytest.raises(ValueError):validate_area(area)
